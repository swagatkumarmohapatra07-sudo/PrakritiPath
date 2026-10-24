"""Fetch open-source reference photographs for the BioTrace species catalogue.

Every card in the biodiversity catalogue can be opened to show several real
photographs and links to further reading. This script fills that gallery with
freely licensed Wikimedia Commons files and records the attribution data that
the UI displays.

Only files whose licence is explicitly free (CC0, public domain, CC BY or
CC BY-SA) are kept. A photograph must also mention the genus (or the full
scientific name) in its title or Commons categories, so a search result for the
wrong organism cannot quietly become "evidence" for a species.

Outputs
-------
frontend/assets/images/species/<class_key>-<n>.jpg
    Optimised local copies, so the site does not hotlink Wikimedia and keeps
    working if a thumbnail URL changes.
backend/app/data/species_images.json
    Attribution metadata, used by ``backend/app/services/species_media.py``.

Usage (from the project root)::

    python -m backend.scripts.fetch_species_images
    python -m backend.scripts.fetch_species_images --per-species 3 --delay 1
    python -m backend.scripts.fetch_species_images --only ficus_religiosa
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
SEED_FILE = DATA_DIR / "species_seed.json"
OUTPUT_FILE = DATA_DIR / "species_images.json"
IMAGE_DIR = PROJECT_ROOT / "frontend" / "assets" / "images" / "species"
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "species_commons.json"
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "PrakritiPath/1.0 (academic biodiversity+tourism project; "
    "https://github.com/swagatkumarmohapatra07-sudo/PrakritiPath)"
)

FREE_LICENCE_PREFIXES = ("cc0", "cc by", "public domain", "pd-", "pdm")
NON_FREE_MARKERS = ("fair use", "non-free", "nonfree", "copyright only")
ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
DOCUMENT_SUFFIXES = (".pdf", ".djvu", ".tif", ".tiff", ".svg", ".gif", ".webm", ".ogv", ".ogg", ".mp4")
NOISE_WORDS = (
    "map", "distribution", "locator", "diagram", "drawing", "illustration",
    "sketch", "painting", "engraving", "lithograph", "stamp", "logo", "icon",
    "herbarium", "specimen", "skull", "skeleton", "bone", "egg", "nest",
    "anatomy", "dissection", "poster", "book", "manuscript",
)
DOCUMENT_CATEGORIES = ("pdf files", "djvu files", "scanned", "book scans", "images from the internet archive")
# A photo can sit in the right taxon category while the organism is incidental
# (a street scene, a person holding fruit, a dog under a tree). Those make poor
# identification references, so category-only matches are rejected when the
# title describes a scene rather than the organism.
SCENE_WORDS = (
    "dog", "cat", "people", "person", "man ", "woman", "child", "street",
    "market", "building", "temple", "boat", "sunset", "landscape", "village",
    "city", "road", "bridge", "festival", "crowd", "portrait",
)
SUBJECT_PENALTIES = (
    "composite", "head", "feather", "wing", "frog", "with ", " on ",
    "close-up", "closeup", "macro", "egg", "nest", "insect", "butterfly",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Wikimedia Commons photographs for BioTrace species.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--per-species", type=int, default=3, help="Maximum photographs per species.")
    parser.add_argument("--only", action="append", default=None, help="Process one class_key (repeatable).")
    parser.add_argument("--refresh", action="store_true", help="Refetch species that already have photographs.")
    parser.add_argument("--refresh-cache", action="store_true", help="Ignore cached API responses.")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between live API requests.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report, but do not write output.")
    return parser.parse_args(argv)


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _clean_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _clean_title(title: str) -> str:
    value = title.removeprefix("File:")
    value = re.sub(r"\.(jpe?g|png|webp|tiff?|svg)$", "", value, flags=re.IGNORECASE)
    value = value.replace("_", " ")
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", text.lower()) if part}


def is_free_licence(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.strip().lower()
    if any(marker in lowered for marker in NON_FREE_MARKERS):
        return False
    return any(lowered.startswith(prefix) for prefix in FREE_LICENCE_PREFIXES)


def scientific_tokens(scientific_name: str) -> set[str]:
    return {token for token in _tokens(scientific_name) if len(token) >= 4}


def common_tokens(common_name: str) -> set[str]:
    generic = {
        "the", "and", "of", "indian", "common", "tree", "bird", "plant",
        "sacred", "fig", "holy", "chinese", "flamboyant", "purple", "black",
        "white", "green", "red", "rose", "ringed", "cattle", "house",
        "eater", "bird", "tree", "flower", "flowers", "leaf", "leaves",
        "plant", "grass", "fruit", "seed", "bean", "pea", "lily", "nut",
    }
    # Four-letter words such as "myna", "crow" or "kite" are too easy to hit in
    # unrelated file names. Require a more distinctive common-name token.
    return {token for token in _tokens(common_name) if len(token) >= 6 and token not in generic}


def title_mentions_species(candidate: dict, scientific_name: str, common_name: str) -> bool:
    """Require the species name in the file title.

    Commons categories are deliberately *not* used for this check. A category
    such as ``Ficus religiosa`` can contain a wide landscape in which the tree
    happens to appear, which is not useful as an identification reference. The
    file title is a much better signal that the uploader meant to photograph the
    organism itself.
    """
    title_tokens = _tokens(candidate.get("title") or "")
    genus = scientific_name.split()[0].lower()
    if genus in title_tokens:
        return True
    tokens = scientific_tokens(scientific_name)
    if len(tokens) >= 2 and tokens <= title_tokens:
        return True
    # A distinctive common-name token is a useful fallback for files such as
    # "Mango fruit Nam Dok Mai", but never override an explicit different name.
    return bool(common_tokens(common_name) & title_tokens)


def category_mentions_species(candidate: dict, scientific_name: str) -> bool:
    categories = _tokens(candidate.get("categories") or "")
    genus = scientific_name.split()[0].lower()
    if genus in categories:
        return True
    tokens = scientific_tokens(scientific_name)
    return len(tokens) >= 2 and tokens <= categories


def candidate_is_usable(candidate: dict, scientific_name: str, common_name: str) -> bool:
    url = candidate.get("url") or ""
    if not url.lower().split("?")[0].endswith(ALLOWED_SUFFIXES):
        return False
    raw_title = (candidate.get("raw_title") or "").lower()
    if raw_title.endswith(DOCUMENT_SUFFIXES):
        return False
    licence = candidate.get("licence")
    if not is_free_licence(licence):
        return False
    if not candidate.get("page_url"):
        return False
    if "by" in (licence or "").lower() and not candidate.get("credit"):
        return False

    categories = (candidate.get("categories") or "").lower()
    if any(marker in categories for marker in DOCUMENT_CATEGORIES):
        return False
    title = f"{candidate.get('title') or ''} {categories}".lower()
    if any(word in title for word in NOISE_WORDS):
        return False

    width = candidate.get("original_width") or candidate.get("width") or 0
    height = candidate.get("original_height") or candidate.get("height") or 0
    if max(width, height) < 900 or min(width, height) < 500:
        return False

    if title_mentions_species(candidate, scientific_name, common_name):
        return True
    # Category membership is curated by Commons editors, but only accept it when
    # the title does not describe an incidental scene.
    if category_mentions_species(candidate, scientific_name):
        title = (candidate.get("title") or "").lower()
        return not any(word in title for word in SCENE_WORDS)
    return False


def score_candidate(candidate: dict, scientific_name: str = "", common_name: str = "") -> float:
    score = 0.0
    title = (candidate.get("title") or "").lower()
    title_tokens = _tokens(title)
    if scientific_name:
        tokens = scientific_tokens(scientific_name)
        if len(tokens) >= 2 and tokens <= title_tokens:
            score += 12
        elif scientific_name.split()[0].lower() in title_tokens:
            score += 8
        elif common_tokens(common_name) & title_tokens:
            score += 3
        if category_mentions_species(candidate, scientific_name):
            score += 2
    if any(word in title for word in SUBJECT_PENALTIES):
        score -= 5
    if any(word in title for word in SCENE_WORDS):
        score -= 8
    categories = (candidate.get("categories") or "").lower()
    if "featured pictures" in categories:
        score += 5
    if "quality images" in categories:
        score += 3
    width = candidate.get("original_width") or candidate.get("width") or 0
    height = candidate.get("original_height") or candidate.get("height") or 0
    if height:
        ratio = width / height
        if ratio >= 1.4:
            score += 2
        elif ratio >= 1.1:
            score += 1
    if width >= 2000:
        score += 2
    elif width >= 1400:
        score += 1
    score += min(width, 4000) / 4000
    return score


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _query(params: dict) -> list[dict]:
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    results = []
    for page in payload.get("query", {}).get("pages", []) or []:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        results.append(
            {
                "title": _clean_title(page.get("title", "")),
                "raw_title": page.get("title", ""),
                "url": _clean_url(info.get("thumburl") or info.get("url")),
                "thumbnail_url": _clean_url(info.get("thumburl") or info.get("url")),
                "page_url": _clean_url(info.get("descriptionurl")),
                "credit": _strip_html((meta.get("Artist") or {}).get("value")),
                "licence": _strip_html((meta.get("LicenseShortName") or {}).get("value")),
                "licence_url": (meta.get("LicenseUrl") or {}).get("value"),
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "original_width": info.get("width"),
                "original_height": info.get("height"),
                "categories": _strip_html((meta.get("Categories") or {}).get("value")),
            }
        )
    return results


def search_commons(search: str, limit: int = 14) -> list[dict]:
    return _query(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": search,
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": "1100",
        }
    )


def list_species_category(scientific_name: str, limit: int = 40) -> list[dict]:
    """List files in ``Category:<scientific name>``.

    Taxon categories are curated by Commons editors and contain many more
    correctly identified photographs than a full-text search returns. A missing
    category is not an error: the caller falls back to search results.
    """
    try:
        return _query(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "generator": "categorymembers",
                "gcmtitle": f"Category:{scientific_name}",
                "gcmtype": "file",
                "gcmlimit": str(limit),
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiurlwidth": "1100",
            }
        )
    except urllib.error.URLError:
        return []


def optimize_image(path: Path, max_width: int = 760) -> None:
    """Resize and re-encode a downloaded reference photo.

    Reference cards only need a modest image. Keeping the files small makes the
    catalogue light on a phone connection while remaining useful when opened in
    the detail dialog. Image metadata is dropped in the process.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a project dependency
        return
    with Image.open(path) as source:
        image = source.convert("RGB")
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        image.save(path, format="JPEG", quality=78, optimize=True, progressive=True)


def download_image(url: str, destination: Path) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise ValueError(f"unexpected content type {content_type!r}")
        payload = response.read()
    if len(payload) < 4096:
        raise ValueError("downloaded file is unexpectedly small")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    optimize_image(destination)
    return destination.stat().st_size


def choose(seed: dict, candidates: list[dict], per_species: int) -> list[dict]:
    scientific = seed["scientific_name"]
    common = seed["common_name"]
    usable = [item for item in candidates if candidate_is_usable(item, scientific, common)]
    usable.sort(key=lambda item: score_candidate(item, scientific, common), reverse=True)
    chosen: list[dict] = []
    seen: set[str] = set()
    for item in usable:
        page = item.get("page_url") or ""
        if not page or page in seen:
            continue
        seen.add(page)
        chosen.append(item)
        if len(chosen) >= per_species:
            break
    return chosen


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    seeds = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only)
        seeds = [item for item in seeds if item.get("class_key") in wanted]
    if not seeds:
        print("No species matched the filter.", file=sys.stderr)
        return 2

    existing: dict[str, list[dict]] = {}
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("species", {})
        except json.JSONDecodeError:
            existing = {}

    cache = load_cache()
    results: dict[str, list[dict]] = dict(existing)
    covered = 0
    missing: list[str] = []
    live_requests = 0
    downloaded = 0

    for index, seed in enumerate(seeds, start=1):
        scientific = seed["scientific_name"]
        class_key = seed["class_key"]
        if results.get(scientific) and not args.refresh:
            covered += 1
            continue

        queries = [scientific, f"{scientific} {seed.get('common_name', '')}"]
        candidates: list[dict] = []
        seen_pages: set[str] = set()
        failed = False
        for query in queries:
            key = f"v1::{query}::14"
            if key in cache and not args.refresh_cache:
                found = cache[key]
            else:
                try:
                    found = search_commons(query)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    print(f"  ! {scientific}: request failed ({exc})", file=sys.stderr)
                    failed = True
                    break
                cache[key] = found
                live_requests += 1
                time.sleep(max(0.0, args.delay))
            for item in found:
                page = item.get("page_url")
                if page and page not in seen_pages:
                    seen_pages.add(page)
                    candidates.append(item)
            if sum(
                1
                for item in candidates
                if candidate_is_usable(item, scientific, seed.get("common_name", ""))
            ) >= args.per_species:
                break

        # Taxon categories often contain better photographs than full-text
        # search. One extra request per species keeps this polite.
        category_key = f"category::{scientific}::{args.per_species}"
        if category_key in cache and not args.refresh_cache:
            category_files = cache[category_key]
        else:
            try:
                category_files = list_species_category(scientific)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                category_files = []
            cache[category_key] = category_files
            live_requests += 1
            time.sleep(max(0.0, args.delay))
        for item in category_files:
            page = item.get("page_url")
            if page and page not in seen_pages:
                seen_pages.add(page)
                candidates.append(item)

        chosen = choose(seed, candidates, args.per_species)
        if not chosen:
            results[scientific] = []
            missing.append(scientific)
            print(f"  {index:>3}. {scientific} — no suitable free photo found")
            if failed:
                continue
            continue

        stored: list[dict] = []
        for item_index, item in enumerate(chosen, start=1):
            filename = f"{class_key}-{item_index}.jpg"
            destination = IMAGE_DIR / filename
            local_url = f"/assets/images/species/{filename}"
            record = {
                "url": local_url,
                "thumbnail_url": local_url,
                "page_url": item.get("page_url"),
                "title": item.get("title"),
                "credit": item.get("credit"),
                "licence": item.get("licence"),
                "licence_url": item.get("licence_url"),
                "source_name": "Wikimedia Commons",
            }
            if not args.dry_run:
                try:
                    if destination.exists() and not args.refresh:
                        pass
                    else:
                        download_image(item["thumbnail_url"] or item["url"], destination)
                        downloaded += 1
                        time.sleep(max(0.0, args.delay / 2))
                except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                    print(f"      ! could not download {item.get('title')}: {exc}", file=sys.stderr)
                    continue
            stored.append(record)

        results[scientific] = stored
        if stored:
            covered += 1
            print(f"  {index:>3}. {scientific} — {len(stored)} photo(s)")

    if not args.dry_run:
        save_cache(cache)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "Wikimedia Commons",
            "note": (
                "Reference photographs for the BioTrace species catalogue. Only free "
                "licences are stored (CC0, public domain, CC BY, CC BY-SA). Each entry "
                "links to its Commons file page, where the full attribution history is "
                "available. Images are downloaded locally so the interface does not "
                "hotlink Wikimedia."
            ),
            "species": {name: results[name] for name in sorted(results)},
        }
        OUTPUT_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nWrote {OUTPUT_FILE}")
        print(f"Downloaded {downloaded} new image file(s) into {IMAGE_DIR}")

    total = sum(len(items) for items in results.values())
    print(
        f"\n{covered}/{len(seeds)} species have photographs; {total} images in total; "
        f"{live_requests} live API request(s)."
    )
    if missing:
        print("Without a suitable photo: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
