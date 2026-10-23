# Datasets

PrakritiPath (BioTrace) ships with a small, curated catalogue so the app works on a
fresh clone with no downloads. Larger AI datasets are **not** committed.

## What is committed

| File | Rows | Purpose |
| ---- | ---- | ------- |
| `backend/app/data/species_seed.json` | 22 | Plant and bird reference catalogue (JSON list) |
| `backend/app/data/tourism_seed_01.jsonl` | 20 | Odisha destinations |
| `backend/app/data/tourism_seed_02.jsonl` | 17 | Odisha destinations |
| `backend/app/data/tourism_seed_03.jsonl` | 33 | Odisha destinations |
| `backend/app/data/categories.py` | — | Valid tourism category slugs and groupings |

`rows` counts are the source of truth; run the tests in
`backend/tests/test_seed.py` to verify the files still parse and stay consistent.

## Species schema

`scientific_name` is the join key used by the classifier. Keep it in the exact
binomial form the model emits.

```json
{
  "class_key": "pavo_cristatus",
  "common_name": "Indian Peafowl",
  "scientific_name": "Pavo cristatus",
  "category": "bird",
  "description": "...",
  "habitat": "...",
  "distribution_information": "...",
  "known_regions": "IN-OR",
  "conservation_status": "...",
  "source": "...",
  "licence_information": "..."
}
```

- `category` must be `plant` or `bird`.
- `known_regions` is a comma-separated list of ISO 3166-2 codes. It is used only
  as a **soft plausibility signal**, never as proof of absence.
- `conservation_status` is scanned for `endangered`, `critically endangered` or
  `vulnerable`; matching records are stored with `derived_sensitive = true` so the
  public API reduces coordinate precision.

## Tourism schema

One JSON object per line (JSONL). Blank lines are ignored.

```json
{
  "name": "Barabati Fort",
  "category": "fort_palace",
  "destination_type": "Fort",
  "city": "Cuttack",
  "district": "Cuttack",
  "locality": "...",
  "query": "Barabati Fort Cuttack",
  "description": "...",
  "significance": "...",
  "tags": "fort, heritage",
  "featured": true,
  "latitude": 20.4847,
  "longitude": 85.8649,
  "osm_id": "way/123456",
  "source_url": "https://www.openstreetmap.org/way/123456",
  "source_name": "OpenStreetMap",
  "licence_information": "ODbL 1.0",
  "last_verified_at": "2026-01-15"
}
```

Rules enforced by the importer and tests:

- `category` must exist in `CATEGORY_BY_SLUG`, otherwise the row is skipped.
- `name`, `category`, `district` and `query` are required by
  `backend/scripts/import_tourism.py`.
- Slugs are derived from `name`; duplicate slugs are rejected by a unique constraint.
- Coordinates are **only** confirmed against OpenStreetMap/Nominatim. Opening hours,
  ticket prices and contact details are never inferred — they stay `null` and the UI
  renders "Not verified".

## Importing and geocoding

```bash
# Insert rows that are already present in the seed files
python -m backend.scripts.import_tourism

# Enrich missing coordinates from Nominatim (<= 1 request/second)
python -m backend.scripts.import_tourism --geocode

# Try a small batch first
python -m backend.scripts.import_tourism --geocode --limit 5
```

Responses are cached in `data/cache/nominatim.json` (git-ignored). Set
`NOMINATIM_USER_AGENT` in `.env` to a descriptive value with a real contact address
before bulk imports; generic strings may be blocked.

## Adding data safely

1. Add new rows in one of the `tourism_seed_*.jsonl` files (or a new numbered file).
2. Cite `source_url`, `source_name` and `licence_information` for every row.
3. Leave unknown facts blank. Do **not** guess hours or prices.
4. Run the pipeline and the tests:

   ```bash
   python -m backend.scripts.import_tourism --geocode
   python -m pytest backend/tests/test_seed.py
   ```

## Large datasets (not committed)

Kaggle/iNaturalist exports, ImageNet-style archives and other multi-gigabyte
datasets are intentionally excluded via `.gitignore` (`datasets/`). Download them
separately and point your training script at the extracted directory. See
[`MODEL_TRAINING.md`](MODEL_TRAINING.md).
