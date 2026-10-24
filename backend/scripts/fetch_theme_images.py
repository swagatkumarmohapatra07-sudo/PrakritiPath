"""Fetch the Odisha cultural photographs used by the interface theme.

The landing hero, the page-hero band and the "living culture" cards use a small,
fixed set of Wikimedia Commons photographs. They are downloaded once, re-encoded
for the web and committed alongside a machine-readable credit file, so the site
never hotlinks an uncredited image and a fresh clone works offline.

Only files whose licence is explicitly free (CC0, CC BY, CC BY-SA, public
domain) are accepted, and each record keeps the author, licence name, licence
URL and Commons file page for attribution.

Usage (from the project root):

    python -m backend.scripts.fetch_theme_images
    python -m backend.scripts.fetch_theme_images --refresh
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scripts.fetch_images import is_free_licence  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "frontend" / "assets" / "images"
CREDITS_FILE = OUTPUT_DIR / "credits.json"
CREDITS_MARKDOWN = OUTPUT_DIR / "CREDITS.md"
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "PrakritiPath/1.0 (academic biodiversity+tourism project; "
    "https://github.com/swagatkumarmohapatra07-sudo/PrakritiPath)"
)

# Curated files. Every title was reviewed by hand so the theme always shows the
# place or practice it claims to show.
TARGETS = [
    {
        "file": "konark-wheel.jpg",
        "title": "File:Konark sun temple-wheel carving.jpg",
        "label": "Stone chariot wheel, Konark Sun Temple",
        "thumb_width": 1600,
        "max_width": 1280,
        "quality": 72,
    },
    {
        "file": "odissi.jpg",
        "title": "File:Sujata Mohapatra 02.jpg",
        "label": "Odissi dancer Sujata Mohapatra",
        "thumb_width": 1200,
        "max_width": 1000,
    },
    {
        "file": "pattachitra.jpg",
        "title": "File:Pattachitra artist at work in Odisha, India.jpg",
        "label": "Pattachitra artist at work in Odisha",
        "thumb_width": 1400,
        "max_width": 1200,
        "quality": 78,
    },
    {
        "file": "rath-yatra.jpg",
        "title": "File:Annual chariot festival 'Jagannath Yatra', Puri Odisha.jpg",
        "label": "Rath Yatra chariot festival, Puri",
        "thumb_width": 1800,
        "max_width": 1500,
        "quality": 76,
    },
    {
        "file": "chilika.jpg",
        "title": "File:Chilika Lake or Chilka in Odisha 01.jpg",
        "label": "Chilika Lake, Odisha",
        "thumb_width": 1600,
        "max_width": 1400,
    },
    {
        "file": "rajarani.jpg",
        "title": "File:Rajarani Temple 01.jpg",
        "label": "Rajarani Temple, Bhubaneswar",
        "thumb_width": 1800,
        "max_width": 1500,
        "quality": 76,
    },
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the curated Odisha cultural photographs used by the theme.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download files that already exist.")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing files.")
    return parser.parse_args(argv)


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def fetch_info(title: str, width: int) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": str(width),
    }
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    pages = payload.get("query", {}).get("pages", []) or []
    if not pages:
        raise RuntimeError(f"No Commons page returned for {title}")
    page = pages[0]
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    return {
        "title": page.get("title", title),
        "url": info.get("thumburl") or info.get("url"),
        "page_url": info.get("descriptionurl"),
        "author": _strip_html((meta.get("Artist") or {}).get("value")),
        "licence": _strip_html((meta.get("LicenseShortName") or {}).get("value")),
        "licence_url": (meta.get("LicenseUrl") or {}).get("value"),
        "width": info.get("width"),
        "height": info.get("height"),
    }


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        destination.write_bytes(response.read())


def optimise(path: Path, max_width: int, quality: int) -> tuple[int, int, int]:
    with Image.open(path) as image:
        image.load()
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        image.save(path, format="JPEG", quality=quality, optimize=True, progressive=True)
        return image.width, image.height, path.stat().st_size


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    credits: list[dict] = []

    for target in TARGETS:
        destination = OUTPUT_DIR / target["file"]
        info = fetch_info(target["title"], target["thumb_width"])
        if not info["url"]:
            print(f"SKIP  {target['file']}: no file URL returned")
            continue
        if not is_free_licence(info["licence"]):
            print(f"SKIP  {target['file']}: licence {info['licence']!r} is not free")
            continue

        record = {
            "file": target["file"],
            "label": target["label"],
            "title": info["title"],
            "author": info["author"],
            "licence": info["licence"],
            "licence_url": info["licence_url"],
            "page_url": info["page_url"],
            "source": "Wikimedia Commons",
        }

        if args.dry_run:
            credits.append(record)
            print(f"DRY   {target['file']}: {info['licence']} by {info['author']}")
            continue

        if destination.exists() and not args.refresh:
            with Image.open(destination) as existing:
                width, height = existing.size
            record["pixels"] = f"{width}x{height}"
            record["bytes"] = destination.stat().st_size
            credits.append(record)
            print(f"KEEP  {target['file']} ({width}x{height})")
            continue

        print(f"GET   {target['file']} <- {info['url']}")
        download(info["url"], destination)
        width, height, size = optimise(destination, target["max_width"], target.get("quality", 80))
        record["pixels"] = f"{width}x{height}"
        record["bytes"] = size
        credits.append(record)
        print(f"OK    {target['file']} ({width}x{height}, {size // 1024} KB)")

    if args.dry_run:
        return 0

    payload = {
        "note": (
            "Odisha cultural photographs used by the BioTrace interface theme. "
            "Only freely licensed Wikimedia Commons files are included."
        ),
        "retrieved": datetime.now(timezone.utc).date().isoformat(),
        "images": credits,
    }
    CREDITS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Image credits",
        "",
        "The interface theme uses the following freely licensed photographs from",
        "Wikimedia Commons. Each file is re-encoded for the web; follow the file",
        "page link for the original and the full licence text.",
        "",
        "| File | Subject | Author | Licence | Source |",
        "| ---- | ------- | ------ | ------- | ------ |",
    ]
    for item in credits:
        lines.append(
            f"| `{item['file']}` | {item['label']} | {item['author'] or 'Unknown'} | "
            f"[{item['licence']}]({item['licence_url'] or ''}) | [Commons]({item['page_url']}) |"
        )
    lines.append("")
    CREDITS_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {CREDITS_FILE.relative_to(PROJECT_ROOT)} and {CREDITS_MARKDOWN.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
