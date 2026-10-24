"""Fetch open-source photographs for every tourism destination.

Images come from Wikimedia Commons, which requires attribution and a link back to
the file page. This script only keeps files whose licence is explicitly free, and
records the author, licence name and licence URL for each one. Nothing is invented:
if a place has no suitable photograph, it is left without images and reported.

The result is written to ``backend/app/data/destination_images.json`` (committed,
so a fresh clone gets the same galleries) and can optionally be loaded into the
current database.

Usage (from the project root):

    python -m backend.scripts.fetch_images
    python -m backend.scripts.fetch_images --limit 3 --per-place 4
    python -m backend.scripts.fetch_images --only barabati-fort --refresh
    python -m backend.scripts.fetch_images --write-db

Politeness: one request per second by default, a descriptive User-Agent, and a
local response cache so re-runs do not hammer the API.
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
OUTPUT_FILE = DATA_DIR / "destination_images.json"
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "commons.json"
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "PrakritiPath/1.0 (academic biodiversity+tourism project; "
    "https://github.com/swagatkumarmohapatra07-sudo/PrakritiPath)"
)

# Licences that permit reuse with attribution. Anything else is rejected.
FREE_LICENCE_PREFIXES = ("cc0", "cc by", "public domain", "pd-", "pdm")
NON_FREE_MARKERS = ("fair use", "non-free", "nonfree", "copyright only")

# File titles/categories that are almost never a photograph of the place.
NOISE_WORDS = (
    "map", "locator", "diagram", "logo", "emblem", "coat of arms", "flag",
    "seal", "plan", "sketch", "drawing", "currency", "stamp",
    "poster", "document", "chart", "graph", "icon", "banner", "template",
    "magazine", "journal", "manuscript", "engraving", "lithograph",
    "scan", "scanned", "book", "volume", "newspaper",
)

# Non-photographic file types on Commons render to a .jpg thumbnail, so the URL
# alone cannot be trusted. These are checked against the original file title.
DOCUMENT_SUFFIXES = (".pdf", ".djvu", ".tif", ".tiff", ".svg", ".gif", ".webm", ".ogv", ".ogg", ".mp4")

DOCUMENT_CATEGORIES = (
    "pdf files", "djvu files", "scanned", "book scans", "media lacking",
    "images from the internet archive",
)

# Words too generic to prove that a photo shows this specific place.
GENERIC_TOKENS = {
    "the", "of", "and", "in", "at", "de", "la", "a", "an", "sri", "shri",
    "odisha", "orissa", "india", "indian",
    "temple", "mandir", "beach", "lake", "fort", "museum", "park", "garden",
    "wildlife", "sanctuary", "waterfall", "cave", "hill", "island", "river",
    "dam", "tower", "palace", "monastery", "church", "mosque", "gurudwara",
    "stupa", "monument", "national", "state", "new", "old", "city", "district",
}

ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Wikimedia Commons photographs for BioTrace destinations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--per-place", type=int, default=5,
                        help="Maximum photographs stored per destination.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N destinations (0 = all).")
    parser.add_argument("--only", action="append", default=None,
                        help="Process one slug (repeatable).")
    parser.add_argument("--refresh", action="store_true",
                        help="Refetch places that already have images.")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Ignore the cached API responses.")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds to wait between live API requests.")
    parser.add_argument("--write-db", action="store_true",
                        help="Also load the results into the current database.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and report, but do not write the JSON file.")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _clean_url(url: str | None) -> str | None:
    """Drop Commons tracking parameters so stored URLs stay stable."""
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _clean_title(title: str) -> str:
    value = title.removeprefix("File:")
    value = re.sub(r"\.(jpe?g|png|webp|tiff?|svg)$", "", value, flags=re.IGNORECASE)
    value = value.replace("_", " ")
    return re.sub(r"\s+", " ", value).strip()


def slugify(name: str) -> str:
    value = name.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-{2,}", "-", value)


def is_free_licence(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.strip().lower()
    if any(marker in lowered for marker in NON_FREE_MARKERS):
        return False
    return any(lowered.startswith(prefix) for prefix in FREE_LICENCE_PREFIXES)


def _tokens(text: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", text.lower()) if part}


def title_matches_place(title: str, place_name: str) -> bool:
    """Cheap relevance guard so an unrelated photo cannot be attached.

    A match requires a shared token that is specific to the place (generic words
    such as "temple" or "lake" do not count). If the place name has no specific
    token, fall back to a substring check.
    """
    specific = _tokens(place_name) - GENERIC_TOKENS
    if not specific:
        compact = re.sub(r"\s+", "", place_name.lower())
        return compact in re.sub(r"\s+", "", title.lower())
    return bool(specific & _tokens(title))


def score_candidate(image: dict) -> float:
    """Rank candidates. Featured/quality images and large landscapes win."""
    score = 0.0
    categories = (image.get("categories") or "").lower()
    if "featured pictures" in categories:
        score += 6
    if "quality images" in categories:
        score += 4

    width = image.get("width") or 0
    height = image.get("height") or 0
    if height:
        ratio = width / height
        if ratio >= 1.4:
            score += 2
        elif ratio >= 1.2:
            score += 1
    if width >= 2000:
        score += 2
    elif width >= 1200:
        score += 1
    score += min(width, 4000) / 4000
    return score


def candidate_is_usable(image: dict, place_name: str) -> bool:
    url = image.get("url") or ""
    if not url.lower().split("?")[0].endswith(ALLOWED_SUFFIXES):
        return False

    raw_title = (image.get("raw_title") or "").lower()
    if raw_title.endswith(DOCUMENT_SUFFIXES):
        return False
    categories = (image.get("categories") or "").lower()
    if any(marker in categories for marker in DOCUMENT_CATEGORIES):
        return False

    licence = image.get("licence")
    if not is_free_licence(licence):
        return False
    if not image.get("page_url"):
        return False
    # Attribution is mandatory for CC BY / CC BY-SA. CC0 and public-domain files
    # may legitimately have no artist field.
    requires_credit = "by" in (licence or "").lower()
    if requires_credit and not image.get("credit"):
        return False

    # Gate on the original file, not the (possibly portrait) thumbnail.
    width = image.get("original_width") or image.get("width") or 0
    height = image.get("original_height") or image.get("height") or 0
    if max(width, height) < 1200 or min(width, height) < 700:
        return False

    title = (image.get("title") or "").lower()
    if any(word in title for word in NOISE_WORDS):
        return False
    return title_matches_place(title, place_name)


def _aspect(image: dict) -> float:
    width = image.get("original_width") or image.get("width") or 0
    height = image.get("original_height") or image.get("height") or 0
    return width / height if height else 0.0


# --------------------------------------------------------------------------- #
# Wikimedia Commons querying
# --------------------------------------------------------------------------- #
def _cache_load() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _cache_save(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def search_commons(search: str, limit: int = 12) -> list[dict]:
    """Return candidate images from Wikimedia Commons for one search phrase."""
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": search,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        # Wikimedia only serves thumbnail widths it has already rendered, so use
        # the width the API hands back (it renders one on request) and never
        # rewrite the size in the browser.
        "iiurlwidth": "1280",
        "iiurlheight": "800",
    }
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.load(response)

    results = []
    for page in payload.get("query", {}).get("pages", []) or []:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        results.append(
            {
                "title": _clean_title(page.get("title", "")),
                "raw_title": page.get("title", ""),
                "url": info.get("thumburl") or info.get("url"),
                "thumbnail_url": info.get("thumburl"),
                "page_url": info.get("descriptionurl"),
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


def relevance(title: str, place_name: str) -> float:
    """How strongly a file title points at this specific place (0 when it does not)."""
    specific = _tokens(place_name) - GENERIC_TOKENS
    title_tokens = _tokens(title or "")
    if not specific:
        compact_name = re.sub(r"\s+", "", place_name.lower())
        compact_title = re.sub(r"\s+", "", (title or "").lower())
        return 3.0 if compact_name and compact_name in compact_title else 0.0
    shared = specific & title_tokens
    if not shared:
        return 0.0
    score = len(shared) / len(specific)
    return score + 1.0 if shared == specific else score


def dedupe_across_places(results: dict[str, list[dict]], names: dict[str, str]) -> int:
    """Keep a photo only at the destination its title best describes.

    Search is fuzzy, so the same picture can qualify for two neighbouring places
    (a crafts museum and the state museum, say). The photo stays with the closest
    name match and is dropped from the others.
    """
    owner: dict[str, tuple[float, str]] = {}
    for slug in sorted(results):
        for image in results[slug]:
            page = image.get("page_url")
            if not page:
                continue
            score = relevance(image.get("title") or "", names.get(slug, slug))
            if page not in owner or score > owner[page][0]:
                owner[page] = (score, slug)

    dropped = 0
    for slug, images in results.items():
        kept = []
        for image in images:
            page = image.get("page_url")
            if page and owner.get(page, (0.0, slug))[1] != slug:
                dropped += 1
                continue
            kept.append(image)
        results[slug] = kept
    return dropped


def select_images(candidates: list[dict], place_name: str, per_place: int) -> list[dict]:
    usable = [item for item in candidates if candidate_is_usable(item, place_name)]

    # Landscape photographs lead the gallery; portraits are kept as a fallback so
    # places with only vertical shots still get a real photo.
    landscape = sorted(
        (item for item in usable if _aspect(item) >= 1.15),
        key=score_candidate,
        reverse=True,
    )
    portrait = sorted(
        (item for item in usable if _aspect(item) < 1.15),
        key=score_candidate,
        reverse=True,
    )

    chosen: list[dict] = []
    seen_pages: set[str] = set()
    for item in landscape + portrait:
        page = item.get("page_url") or ""
        if page in seen_pages:
            continue
        seen_pages.add(page)
        chosen.append(
            {
                "url": _clean_url(item["url"]),
                "thumbnail_url": _clean_url(item.get("thumbnail_url") or item["url"]),
                "page_url": _clean_url(page),
                "title": item.get("title"),
                "credit": item.get("credit"),
                "licence": item.get("licence"),
                "licence_url": item.get("licence_url"),
                "width": item.get("width"),
                "height": item.get("height"),
                "source_name": "Wikimedia Commons",
            }
        )
        if len(chosen) >= per_place:
            break
    return chosen


# --------------------------------------------------------------------------- #
# Destination list
# --------------------------------------------------------------------------- #
def load_destinations() -> list[dict]:
    """Read the committed seed files; the slug matches the database exactly."""
    places: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob("tourism_seed_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            slug = slugify(record["name"])
            places.setdefault(
                slug,
                {
                    "slug": slug,
                    "name": record["name"],
                    "district": record.get("district"),
                    "query": record.get("query"),
                },
            )
    return [places[slug] for slug in sorted(places)]


def build_queries(place: dict) -> list[str]:
    """Several phrasings, tried in order until enough usable photos are found."""
    name = str(place["name"])
    plain = re.sub(r"[^\w\s&-]", " ", name)
    plain = re.sub(r"\s+", " ", plain).strip()
    district = place.get("district")

    candidates = [
        place.get("query"),
        f"{name} Odisha",
        name,
        plain,
        f"{plain} Odisha",
        f"{name} {district}" if district else None,
    ]
    queries: list[str] = []
    for item in candidates:
        if item and item not in queries:
            queries.append(str(item))
    return queries


def build_query(place: dict) -> str:
    """Backwards-compatible single query (used by tests)."""
    return build_queries(place)[0]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    existing: dict[str, list[dict]] = {}
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("places", {})
        except json.JSONDecodeError:
            existing = {}

    cache = _cache_load()
    all_destinations = load_destinations()
    names_by_slug = {item["slug"]: item["name"] for item in all_destinations}
    destinations = all_destinations
    if args.only:
        wanted = set(args.only)
        destinations = [item for item in destinations if item["slug"] in wanted]
    if args.limit:
        destinations = destinations[: args.limit]

    if not destinations:
        print("No destinations matched the filter.", file=sys.stderr)
        return 2

    results: dict[str, list[dict]] = dict(existing)
    fetched = 0
    covered = 0
    empty: list[str] = []

    for index, place in enumerate(destinations, start=1):
        slug = place["slug"]
        if slug in existing and existing[slug] and not args.refresh:
            covered += int(bool(existing[slug]))
            continue

        candidates: list[dict] = []
        seen_pages: set[str] = set()
        failed = False
        for query in build_queries(place):
            cache_key = f"v3::{query}::12"
            if cache_key in cache and not args.refresh_cache:
                found = cache[cache_key]
            else:
                try:
                    found = search_commons(query, limit=12)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    print(f"  ! {slug}: request failed ({exc})", file=sys.stderr)
                    failed = True
                    break
                cache[cache_key] = found
                fetched += 1
                time.sleep(max(0.0, args.delay))

            for item in found:
                page = item.get("page_url")
                if page and page not in seen_pages:
                    seen_pages.add(page)
                    candidates.append(item)

            usable_now = sum(
                1 for item in candidates if candidate_is_usable(item, place["name"])
            )
            if usable_now >= args.per_place:
                break

        if failed and not candidates:
            empty.append(slug)
            continue

        chosen = select_images(candidates, place["name"], args.per_place)
        if chosen:
            results[slug] = chosen
            covered += 1
            print(f"  {index:>3}. {place['name']} — {len(chosen)} photo(s)")
        else:
            results[slug] = []
            empty.append(slug)
            print(f"  {index:>3}. {place['name']} — no suitable free photo found")

    if not args.dry_run:
        _cache_save(cache)
        dropped = dedupe_across_places(results, names_by_slug)
        if dropped:
            print(f"Removed {dropped} photo(s) duplicated across destinations.")
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "Wikimedia Commons",
            "note": (
                "Open-source photographs with per-file attribution. Only free licences "
                "are stored (CC0, public domain, CC BY, CC BY-SA). Each entry links to its "
                "Commons file page, which is required for correct attribution."
            ),
            "places": {slug: results[slug] for slug in sorted(results)},
        }
        OUTPUT_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nWrote {OUTPUT_FILE}")

        if args.write_db:
            from backend.app.database import SessionLocal, init_db
            from backend.app.seed import seed_destination_images

            init_db()
            db = SessionLocal()
            try:
                created = seed_destination_images(db)
                print(f"Inserted {created} image row(s) into the database.")
            finally:
                db.close()

    total_images = sum(len(items) for items in results.values())
    print(
        f"\n{covered}/{len(destinations)} destinations have photographs; "
        f"{total_images} images in total; {fetched} live API request(s)."
    )
    if empty:
        print("Without a suitable photo: " + ", ".join(empty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
