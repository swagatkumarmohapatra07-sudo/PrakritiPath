"""Canonical tourism category taxonomy.

The API exposes this list so the frontend never hardcodes labels or icons.
``group`` is used for the coarse filter chips; ``icon`` maps to a Lucide icon.
"""

from __future__ import annotations

TOURISM_CATEGORIES: list[dict[str, str]] = [
    {
        "slug": "temple",
        "label": "Temples",
        "group": "Religious sites",
        "icon": "landmark",
        "description": "Hindu temples, shrines and pilgrimage sites.",
    },
    {
        "slug": "mosque",
        "label": "Mosques & Islamic heritage",
        "group": "Religious sites",
        "icon": "moon-star",
        "description": "Mosques, dargahs and Islamic heritage places.",
    },
    {
        "slug": "church",
        "label": "Churches",
        "group": "Religious sites",
        "icon": "church",
        "description": "Churches and Christian heritage sites.",
    },
    {
        "slug": "buddhist",
        "label": "Buddhist sites",
        "group": "Religious sites",
        "icon": "flower",
        "description": "Monasteries, stupas and Buddhist archaeological sites.",
    },
    {
        "slug": "jain",
        "label": "Jain heritage",
        "group": "Religious sites",
        "icon": "hand",
        "description": "Jain temples, caves and heritage sites.",
    },
    {
        "slug": "gurudwara",
        "label": "Gurudwaras",
        "group": "Religious sites",
        "icon": "book-open",
        "description": "Sikh gurudwaras and community spaces.",
    },
    {
        "slug": "museum",
        "label": "Museums & galleries",
        "group": "Culture & heritage",
        "icon": "building-2",
        "description": "State museums, science centres and specialist collections.",
    },
    {
        "slug": "monument",
        "label": "Monuments & archaeology",
        "group": "Culture & heritage",
        "icon": "history",
        "description": "Protected monuments, cave sites and excavated remains.",
    },
    {
        "slug": "fort_palace",
        "label": "Forts & palaces",
        "group": "Culture & heritage",
        "icon": "castle",
        "description": "Forts, palaces and heritage buildings.",
    },
    {
        "slug": "cultural",
        "label": "Craft & culture",
        "group": "Culture & heritage",
        "icon": "palette",
        "description": "Craft villages, haats and living cultural traditions.",
    },
    {
        "slug": "beach",
        "label": "Beaches",
        "group": "Nature & outdoors",
        "icon": "waves",
        "description": "Coastal beaches and shoreline attractions.",
    },
    {
        "slug": "waterfall_lake",
        "label": "Lakes & waterfalls",
        "group": "Nature & outdoors",
        "icon": "droplets",
        "description": "Lakes, lagoons, dams and waterfalls.",
    },
    {
        "slug": "wildlife",
        "label": "Wildlife & forests",
        "group": "Nature & outdoors",
        "icon": "trees",
        "description": "Sanctuaries, national parks and nature destinations.",
    },
    {
        "slug": "park_garden",
        "label": "Parks & gardens",
        "group": "Nature & outdoors",
        "icon": "flower-2",
        "description": "City parks, botanical gardens and recreation areas.",
    },
    {
        "slug": "other",
        "label": "Other places",
        "group": "More to explore",
        "icon": "map-pin",
        "description": "Other verified visitor destinations.",
    },
]

CATEGORY_BY_SLUG = {item["slug"]: item for item in TOURISM_CATEGORIES}

CATEGORY_GROUPS = ["Religious sites", "Culture & heritage", "Nature & outdoors", "More to explore"]
