"""Reference photographs and further-reading links for catalogue species.

The photographs are fetched by ``backend/scripts/fetch_species_images.py`` and
stored locally with their Wikimedia Commons attribution. The links below are
deliberate *search or article* links: they point to sources a reader can check,
rather than asserting a fact that the project has not verified.

Nothing in this module invents an image, a record or a conservation status. A
species with no suitable free photograph simply returns an empty gallery.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "species_images.json"

# iNaturalist place id for Odisha (resolved from the public places API).
ODHISHA_INAT_PLACE_ID = 8907


def _load() -> dict[str, list[dict]]:
    if not DATA_FILE.exists():
        return {}
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    species = payload.get("species") or {}
    return {str(name): list(items) for name, items in species.items() if name}


_IMAGES = _load()


def images_for(scientific_name: str | None) -> list[dict]:
    if not scientific_name:
        return []
    return list(_IMAGES.get(scientific_name, []))


def cover_for(scientific_name: str | None) -> dict | None:
    images = images_for(scientific_name)
    return images[0] if images else None


def _article_url(scientific_name: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(scientific_name.replace(" ", "_"), safe="_")


def sources_for(
    scientific_name: str,
    common_name: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return honest further-reading links for one species.

    Each entry is a page a visitor can inspect. Search links are labelled as
    searches, and no claim is made that a particular record exists there.
    """
    name = quote(scientific_name)
    sources = [
        {
            "label": f"Wikipedia · {scientific_name}",
            "url": _article_url(scientific_name),
            "kind": "reference",
            "note": "Encyclopaedic overview and taxonomy. Wikipedia is a starting point; check its cited sources.",
        },
        {
            "label": "GBIF species search",
            "url": f"https://www.gbif.org/species/search?q={name}",
            "kind": "occurrence",
            "note": "Global Biodiversity Information Facility: taxonomy backbone and occurrence datasets.",
        },
        {
            "label": "iNaturalist · Odisha observations",
            "url": (
                "https://www.inaturalist.org/observations"
                f"?place_id={ODHISHA_INAT_PLACE_ID}&taxon_name={name}&verifiable=any"
            ),
            "kind": "occurrence",
            "note": "Community observations filtered to Odisha. These are volunteer records, not project data.",
        },
        {
            "label": "IUCN Red List search",
            "url": f"https://www.iucnredlist.org/search?query={name}&searchType=species",
            "kind": "conservation",
            "note": "Check the current global assessment. The catalogue's status text is a snapshot, not a live feed.",
        },
        {
            "label": "Wikimedia Commons",
            "url": f"https://commons.wikimedia.org/w/index.php?search={name}",
            "kind": "media",
            "note": "Source of the gallery photographs. Each file page carries the full attribution and licence.",
        },
    ]
    if (category or "").lower() == "plant":
        sources.append(
            {
                "label": "Plants of the World Online (Kew)",
                "url": f"https://powo.science.kew.org/results?q={name}",
                "kind": "reference",
                "note": "Accepted botanical name and distribution, maintained by the Royal Botanic Gardens, Kew.",
            }
        )
    return sources


def odisha_note(known_regions: str | None) -> str:
    regions = (known_regions or "").strip()
    if not regions:
        return (
            "No curated distribution note is recorded for this species. Absence of a note "
            "does not mean the species is absent from Odisha."
        )
    if "IN-OR" in regions.upper() or "ODISHA" in regions.upper():
        return (
            "Listed for Odisha (IN-OR) in the project's curated distribution field. This is a "
            "soft plausibility signal for identification checks, not proof that the species is "
            "present at any particular site."
        )
    return (
        f"Curated distribution field: {regions}. The project has not verified a specific "
        "Odisha occurrence for this species."
    )
