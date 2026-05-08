# Additional Location Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Philadelphia, Montreal, Toronto, Vancouver, and DC as manifest-driven commute cartogram locations, stopping any city that is blocked by gated source access without blocking earlier cities.

**Architecture:** Extend the existing `LOCATION_CONFIGS` manifest one city at a time. Each city uses filtered labeled `areas` plus broader `landMask` coverage, static GTFS source download, route allowlists verified from generated GTFS, city smoke checks, and frontend/Worker routing updates.

**Tech Stack:** Python 3 standard library, static GTFS ZIP files, GeoJSON/ArcGIS FeatureServer sources, Overpass JSON, static JavaScript/HTML, Cloudflare Worker.

---

## File Map

- Modify `build_commute_site_data.py`: constants, manifests, source download support where needed.
- Modify `scripts/check_commute_data.py`: add dataset paths, route smoke checks, land-mask checks.
- Modify `site/app.js`: add supported city slugs and emoji fallbacks.
- Modify `site/index.html`: add supported deploy slugs.
- Modify `src/worker.js`: add route prefixes.
- Generate `data/<slug>/...` source files and `site/data/<slug>/commute_map_data.json` for each successful city.

## Task 1: Add Shared Multi-City Validation Hooks

**Files:**
- Modify: `scripts/check_commute_data.py`

- [ ] **Step 1: Add future dataset paths**

Add these entries to `DATASETS` after `chicago`:

```python
    "philadelphia": ROOT / "site" / "data" / "philadelphia" / "commute_map_data.json",
    "montreal": ROOT / "site" / "data" / "montreal" / "commute_map_data.json",
    "toronto": ROOT / "site" / "data" / "toronto" / "commute_map_data.json",
    "vancouver": ROOT / "site" / "data" / "vancouver" / "commute_map_data.json",
    "dc": ROOT / "site" / "data" / "dc" / "commute_map_data.json",
```

Update the missing-data skip in `main` to skip every future city until generated:

```python
        if city in {"philadelphia", "montreal", "toronto", "vancouver", "dc"} and not path.exists():
            print(f"{city}: skipped; data not generated yet")
            continue
```

- [ ] **Step 2: Run checker to verify future cities skip**

Run:

```bash
python3 scripts/check_commute_data.py
```

Expected output includes:

```text
nyc: ok
boston: ok
chicago: ok
philadelphia: skipped; data not generated yet
montreal: skipped; data not generated yet
toronto: skipped; data not generated yet
vancouver: skipped; data not generated yet
dc: skipped; data not generated yet
```

- [ ] **Step 3: Commit**

Run:

```bash
git add scripts/check_commute_data.py
git commit -m "test: prepare checks for additional locations"
```

## Task 2: Add Philadelphia

**Files:**
- Modify: `build_commute_site_data.py`
- Modify: `scripts/check_commute_data.py`
- Modify: `site/app.js`
- Modify: `site/index.html`
- Modify: `src/worker.js`
- Generate: `data/philadelphia/`
- Generate: `site/data/philadelphia/commute_map_data.json`

- [ ] **Step 1: Add Philadelphia constants and manifest**

Add `PHILADELPHIA_DATA_DIR`, GTFS path, label area path, land area path, streets path, and GTFS URL constants near the existing city constants.

Use SEPTA static GTFS from:

```python
PHILADELPHIA_SEPTA_GTFS_URL = "https://github.com/septadev/GTFS/releases/latest/download/gtfs_public.zip"
```

Start with route inclusion by route type for rail-like GTFS routes:

```python
"include_route_types": {"0", "1"},
"include_route_ids": set(),
"exclude_route_ids": set(),
```

Set `station_source` to `gtfs_parent_stations`.

- [ ] **Step 2: Build Philadelphia once for route inspection**

Run:

```bash
python3 build_commute_site_data.py --city philadelphia
```

If a downloaded SEPTA ZIP contains nested GTFS ZIPs instead of GTFS text files at the root, add a small manifest option such as `gtfs_member` and update the GTFS reader to open that nested ZIP for Philadelphia.

- [ ] **Step 3: Inspect Philadelphia route IDs**

Run:

```bash
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("site/data/philadelphia/commute_map_data.json").read_text()); print(sorted(data["routeStyles"])); print(sorted(station["name"] for station in data["stations"])[:40])'
```

Use the output to replace broad route-type inclusion with an explicit `PHILADELPHIA_RAPID_TRANSIT_ROUTES` allowlist. Include only fixed-stop urban rail/trolley service selected by policy; exclude SEPTA Regional Rail and ordinary buses.

- [ ] **Step 4: Add Philadelphia checker smoke tests**

Add `PHILADELPHIA_RAPID_TRANSIT_ROUTES` in `scripts/check_commute_data.py` from the inspected route IDs. Add `check_philadelphia(data)` that verifies:

```python
route_ids = set(data["routeStyles"])
require(PHILADELPHIA_RAPID_TRANSIT_ROUTES.issubset(route_ids), "philadelphia missing one or more rapid-transit routes")
require(route_ids.issubset(PHILADELPHIA_RAPID_TRANSIT_ROUTES), "philadelphia includes non-rapid-transit route ids")
require(any(area.get("name") == "Philadelphia" for area in data["areas"]), "philadelphia missing Philadelphia area")
station_names = {station.get("name") for station in data["stations"]}
require("15th St Station" in station_names or "City Hall Station" in station_names or "City Hall" in station_names, "philadelphia missing expected Center City station")
require_land_mask_contains(data, -75.2750, 39.9800, "philadelphia land mask missing Lower Merion")
```

Call it from `main` when `city == "philadelphia"`.

- [ ] **Step 5: Add Philadelphia frontend routing**

Add `philadelphia` to:

```javascript
const SUPPORTED_CITY_SLUGS = new Set(["nyc", "boston", "chicago", "philadelphia"]);
```

in `site/app.js`, to the `supportedSlugs` set in `site/index.html`, and to `PATH_PREFIXES` in `src/worker.js`.

Add an emoji fallback:

```javascript
philadelphia: ["🚇", "🔔", "🏙️", "🚉", "🌳"],
```

- [ ] **Step 6: Rebuild and verify Philadelphia**

Run:

```bash
python3 build_commute_site_data.py --city philadelphia
python3 scripts/check_commute_data.py
npm run check:js
```

Expected: all existing cities pass and `philadelphia: ok`.

- [ ] **Step 7: Commit Philadelphia**

Run:

```bash
git add build_commute_site_data.py scripts/check_commute_data.py site/app.js site/index.html src/worker.js data/philadelphia site/data/philadelphia
git commit -m "feat: add Philadelphia commute data"
```

## Task 3: Add Montreal

**Files:**
- Modify: same source/check/frontend files as Task 2.
- Generate: `data/montreal/`
- Generate: `site/data/montreal/commute_map_data.json`

- [ ] **Step 1: Add Montreal manifest**

Use STM GTFS:

```python
MONTREAL_STM_GTFS_URL = "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip"
```

Start with `include_route_types: {"1"}` and inspect route IDs. Set label areas to Montreal, Laval, and Longueuil if boundary source names match. Set broader land coverage to the same regional boundary source without the label filter.

- [ ] **Step 2: Build and inspect Montreal route IDs**

Run:

```bash
python3 build_commute_site_data.py --city montreal
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("site/data/montreal/commute_map_data.json").read_text()); print(sorted(data["routeStyles"])); print(sorted(station["name"] for station in data["stations"])[:40])'
```

Replace broad inclusion with explicit `MONTREAL_METRO_ROUTES`.

- [ ] **Step 3: Add Montreal smoke checks and frontend routing**

Add `check_montreal(data)` with route allowlist validation, a central station check such as `Berri-UQAM`, and an unlabeled land-mask point in a nearby municipality inside the map extent.

Add `montreal` to frontend slug sets, Worker prefixes, and emoji fallback.

- [ ] **Step 4: Verify and commit Montreal**

Run:

```bash
python3 build_commute_site_data.py --city montreal
python3 scripts/check_commute_data.py
npm run check:js
git add build_commute_site_data.py scripts/check_commute_data.py site/app.js site/index.html src/worker.js data/montreal site/data/montreal
git commit -m "feat: add Montreal commute data"
```

## Task 4: Add Toronto

**Files:**
- Modify: same source/check/frontend files as Task 2.
- Generate: `data/toronto/`
- Generate: `site/data/toronto/commute_map_data.json`

- [ ] **Step 1: Add Toronto manifest**

Use TTC GTFS from Toronto Open Data:

```python
TORONTO_TTC_GTFS_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7795b45e-e65a-4465-81fc-c36b9dfff169/resource/cfb6b2b8-6191-41e3-bda1-b175c51148cb/download/TTC%20Routes%20and%20Schedules%20Data.zip"
```

Start with route-type filtering for subway/metro and then inspect route IDs. Exclude buses and streetcars in this phase unless the user changes policy.

- [ ] **Step 2: Build and inspect Toronto route IDs**

Run:

```bash
python3 build_commute_site_data.py --city toronto
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("site/data/toronto/commute_map_data.json").read_text()); print(sorted(data["routeStyles"])); print(sorted(station["name"] for station in data["stations"])[:40])'
```

Replace broad inclusion with explicit `TORONTO_SUBWAY_ROUTES`.

- [ ] **Step 3: Add Toronto smoke checks and frontend routing**

Add `check_toronto(data)` with route allowlist validation, a central station check such as `Union Station` or `Bloor-Yonge`, and an unlabeled land-mask point in a nearby municipality inside the map extent.

Add `toronto` to frontend slug sets, Worker prefixes, and emoji fallback.

- [ ] **Step 4: Verify and commit Toronto**

Run:

```bash
python3 build_commute_site_data.py --city toronto
python3 scripts/check_commute_data.py
npm run check:js
git add build_commute_site_data.py scripts/check_commute_data.py site/app.js site/index.html src/worker.js data/toronto site/data/toronto
git commit -m "feat: add Toronto commute data"
```

## Task 5: Add Vancouver

**Files:**
- Modify: same source/check/frontend files as Task 2.
- Generate: `data/vancouver/`
- Generate: `site/data/vancouver/commute_map_data.json`

- [ ] **Step 1: Add Vancouver manifest**

Use TransLink GTFS:

```python
VANCOUVER_TRANSLINK_GTFS_URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"
```

Include TransLink attribution in UI metadata:

```text
Route and arrival data used in this product or service is provided by permission of TransLink. TransLink assumes no responsibility for the accuracy or currency of the Data used in this product or service.
```

Start with SkyTrain and ferry route types, then inspect route IDs. Exclude ordinary buses and West Coast Express.

- [ ] **Step 2: Build and inspect Vancouver route IDs**

Run:

```bash
python3 build_commute_site_data.py --city vancouver
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("site/data/vancouver/commute_map_data.json").read_text()); print(sorted(data["routeStyles"])); print(sorted(station["name"] for station in data["stations"])[:40])'
```

Replace broad inclusion with explicit `VANCOUVER_RAPID_TRANSIT_ROUTES`.

- [ ] **Step 3: Add Vancouver smoke checks and frontend routing**

Add `check_vancouver(data)` with route allowlist validation, a central station check such as `Waterfront`, and an unlabeled land-mask point in a nearby municipality inside the map extent.

Add `vancouver` to frontend slug sets, Worker prefixes, and emoji fallback.

- [ ] **Step 4: Verify and commit Vancouver**

Run:

```bash
python3 build_commute_site_data.py --city vancouver
python3 scripts/check_commute_data.py
npm run check:js
git add build_commute_site_data.py scripts/check_commute_data.py site/app.js site/index.html src/worker.js data/vancouver site/data/vancouver
git commit -m "feat: add Vancouver commute data"
```

## Task 6: Try DC Last

**Files:**
- Modify: same source/check/frontend files as Task 2 if access works.
- Generate: `data/dc/`
- Generate: `site/data/dc/commute_map_data.json`

- [ ] **Step 1: Add DC manifest with WMATA Rail GTFS URL**

Use:

```python
DC_WMATA_RAIL_GTFS_URL = "https://api.wmata.com/gtfs/rail-gtfs-static.zip"
```

If the download returns unauthorized, stop this task and report that WMATA requires an API key. Do not commit partial DC code unless it cleanly skips missing credentials.

- [ ] **Step 2: If access works, build and inspect DC route IDs**

Run:

```bash
python3 build_commute_site_data.py --city dc
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("site/data/dc/commute_map_data.json").read_text()); print(sorted(data["routeStyles"])); print(sorted(station["name"] for station in data["stations"])[:40])'
```

Replace broad inclusion with explicit `DC_METRORAIL_ROUTES`.

- [ ] **Step 3: Add DC smoke checks and frontend routing only if data builds**

Add `check_dc(data)` with route allowlist validation, a central station check such as `Metro Center`, and an unlabeled land-mask point in a nearby Maryland or Virginia jurisdiction inside the map extent.

Add `dc` to frontend slug sets, Worker prefixes, and emoji fallback.

- [ ] **Step 4: Verify and commit DC if access works**

Run:

```bash
python3 build_commute_site_data.py --city dc
python3 scripts/check_commute_data.py
npm run check:js
git add build_commute_site_data.py scripts/check_commute_data.py site/app.js site/index.html src/worker.js data/dc site/data/dc
git commit -m "feat: add DC commute data"
```

## Task 7: Final Verification

**Files:**
- Read: generated data and route files.

- [ ] **Step 1: Rebuild every successful city**

Run one command per supported city in `LOCATION_CONFIGS`:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 build_commute_site_data.py --city chicago
python3 build_commute_site_data.py --city philadelphia
python3 build_commute_site_data.py --city montreal
python3 build_commute_site_data.py --city toronto
python3 build_commute_site_data.py --city vancouver
```

Only include `dc` if Task 6 succeeded:

```bash
python3 build_commute_site_data.py --city dc
```

- [ ] **Step 2: Run full checks**

Run:

```bash
npm run check
```

Expected: data checks pass for every generated city and JS syntax checks pass.

- [ ] **Step 3: Review git status**

Run:

```bash
git status --short
```

Expected: only `tmp/` remains untracked unless intentionally ignored generated files are present.
