# Multi-Location Manifest And Chicago Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor NYC/Boston city support into a reusable location manifest, prove the refactor preserves existing generated data, then add Chicago CTA `L` support.

**Architecture:** Keep the current standard-library Python builder and static frontend. Move city-specific source, route, coverage, and UI settings into a nested manifest consumed by generic builder helpers. Preserve unique behavior through named hooks for NYC station data, NYC external land, and the Staten Island Ferry.

**Tech Stack:** Python 3 standard library, GTFS static ZIP files, GeoJSON, ArcGIS FeatureServer GeoJSON queries, Overpass API JSON, static HTML/CSS/JavaScript, Cloudflare Worker.

---

## File Map

- Modify `build_commute_site_data.py`: location manifest, generic source ensure hooks, route filtering, Chicago config.
- Modify `scripts/check_commute_data.py`: load supported cities dynamically or add Chicago explicitly; add stronger graph invariants.
- Create `scripts/compare_commute_data.py`: canonical JSON comparison for refactor baselines.
- Modify `site/app.js`: supported city slug list; Chicago slug detection.
- Modify `site/index.html`: supported deploy slug list and dataset-driven visible source/note copy.
- Modify `src/worker.js`: add `/chicago` route prefix.
- Generated, not committed unless already tracked by project convention: `site/data/<city>/commute_map_data.json`.

## Task 1: Add Refactor Golden Comparison Tool

**Files:**
- Create: `scripts/compare_commute_data.py`

- [ ] **Step 1: Create the comparison script**

Add this file:

```python
#!/usr/bin/env python3
"""Compare generated commute data JSON files after canonical normalization."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def load(path: Path) -> Any:
    try:
        return canonicalize(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        print(f"missing file: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as error:
        print(f"invalid JSON in {path}: {error}", file=sys.stderr)
        raise SystemExit(2)


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: compare_commute_data.py BASELINE CURRENT", file=sys.stderr)
        raise SystemExit(2)

    baseline_path = Path(sys.argv[1])
    current_path = Path(sys.argv[2])
    if load(baseline_path) != load(current_path):
        print(f"commute data differs: {baseline_path} != {current_path}", file=sys.stderr)
        raise SystemExit(1)

    print(f"commute data matches: {current_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax-check the script**

Run:

```bash
python3 -m py_compile scripts/compare_commute_data.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add scripts/compare_commute_data.py
git commit -m "test: add commute data comparison helper"
```

## Task 2: Capture NYC And Boston Baselines

**Files:**
- Read: `build_commute_site_data.py`
- Generated temporary files under: `tmp/baselines/`

- [ ] **Step 1: Build current NYC data**

Run:

```bash
python3 build_commute_site_data.py --city nyc
```

Expected output includes:

```text
Wrote /Users/samhitov/dev/codex/nyc-cartogram/site/data/commute_map_data.json
```

- [ ] **Step 2: Build current Boston data**

Run:

```bash
python3 build_commute_site_data.py --city boston
```

Expected output includes:

```text
Wrote /Users/samhitov/dev/codex/nyc-cartogram/site/data/boston/commute_map_data.json
```

- [ ] **Step 3: Save temporary baselines**

Run:

```bash
mkdir -p tmp/baselines
cp site/data/nyc/commute_map_data.json tmp/baselines/nyc.json
cp site/data/boston/commute_map_data.json tmp/baselines/boston.json
```

Expected: no output and both baseline files exist.

- [ ] **Step 4: Confirm baseline comparison works**

Run:

```bash
python3 scripts/compare_commute_data.py tmp/baselines/nyc.json site/data/nyc/commute_map_data.json
python3 scripts/compare_commute_data.py tmp/baselines/boston.json site/data/boston/commute_map_data.json
```

Expected output includes:

```text
commute data matches: site/data/nyc/commute_map_data.json
commute data matches: site/data/boston/commute_map_data.json
```

## Task 3: Refactor Builder Manifest Without Behavior Changes

**Files:**
- Modify: `build_commute_site_data.py`

- [ ] **Step 1: Replace flat `CITY_CONFIGS` with nested `LOCATION_CONFIGS`**

In `build_commute_site_data.py`, replace `CITY_CONFIGS = { ... }` with a nested manifest that preserves existing values. Keep constants such as `BOSTON_RAPID_TRANSIT_ROUTES` and paths unchanged.

The new shape must expose these keys for each slug:

```python
LOCATION_CONFIGS = {
    "nyc": {
        "slug": "nyc",
        "display_name": "New York City",
        "short_name": "NYC",
        "area_kind": "boroughs",
        "output_path": SITE_DATA_PATH,
        "city_output_path": ROOT / "site" / "data" / "nyc" / "commute_map_data.json",
        "transit": {
            "gtfs_path": NYC_GTFS_PATH,
            "station_source": "nyc_station_json",
            "include_route_types": {"1"},
            "include_route_ids": {"SI"},
            "exclude_route_ids": set(),
        },
        "coverage": {
            "areas_path": NYC_BOROUGHS_PATH,
            "area_name_property": "boroname",
            "area_include_names": None,
        },
        "context": {
            "parks_path": NYC_PARKS_PATH,
            "park_area_property": "shape_area",
            "park_area_min": 70000.0,
            "streets_path": NYC_STREETS_PATH,
            "external_land": "nyc_counties",
            "counties_kml_path": NYC_COUNTIES_KML_ZIP_PATH,
        },
        "hooks": {
            "manual_connection": "staten_island_ferry",
        },
        "ui": {
            "search_query_suffix": "New York City",
            "search_viewbox": "-74.30,40.95,-73.65,40.45",
            "share_text": "Explore New York City by subway commute time with this interactive transit cartogram.",
            "transit_note": (
                "Travel times are estimated from MTA GTFS subway trips plus short walking access to and "
                "from stations. The map is transit-only for now and does not yet include bus service "
                "or real-time schedules. The only ferry service included is the Staten Island Ferry."
            ),
            "data_credits": "MTA GTFS, NYC Open Data, OpenStreetMap",
            "download_prefix": "nyc-commute-cartogram",
            "url_label": "castrio.me/nyc",
            "source_links": [
                {"label": "NYC borough boundaries", "url": "https://data.cityofnewyork.us/resource/gthc-hcne.geojson?$limit=100", "emoji": "nyc"},
                {"label": "MTA GTFS subway data", "url": "https://new.mta.info/developers", "emoji": "transit"},
                {"label": "OpenStreetMap streets", "url": "https://www.openstreetmap.org/", "emoji": "maps"},
                {"label": "NYC Parks open space", "url": "https://www.nycgovparks.org/about/health-and-safety-guide/open-data", "emoji": "parks"},
            ],
        },
    },
    "boston": {
        "slug": "boston",
        "display_name": "Boston",
        "short_name": "Boston",
        "area_kind": "municipalities",
        "output_path": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
        "city_output_path": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
        "transit": {
            "gtfs_path": BOSTON_GTFS_PATH,
            "gtfs_url": BOSTON_MBTA_GTFS_URL,
            "station_source": "gtfs_parent_stations",
            "include_route_types": set(),
            "include_route_ids": BOSTON_RAPID_TRANSIT_ROUTES,
            "exclude_route_ids": set(),
        },
        "coverage": {
            "areas_path": BOSTON_AREAS_PATH,
            "areas_url": BOSTON_MUNICIPALITIES_URL,
            "area_name_property": "TOWNNAME",
            "area_include_names": set(BOSTON_MUNICIPALITIES),
        },
        "context": {
            "parks_path": BOSTON_OPEN_SPACE_PATH,
            "park_area_property": "GIS_ACRES",
            "park_area_min": 1.6,
            "streets_path": BOSTON_STREETS_PATH,
        },
        "hooks": {
            "manual_connection": None,
        },
        "ui": {
            "search_query_suffix": "Massachusetts",
            "search_viewbox": "-71.30,42.45,-70.85,42.15",
            "share_text": "Explore Boston by MBTA rapid-transit commute time with this interactive transit cartogram.",
            "transit_note": (
                "Travel times are estimated from MBTA GTFS rapid-transit trips plus short walking access "
                "to and from stations. The map is transit-only for now and does not include bus service, "
                "commuter rail, or real-time schedules."
            ),
            "data_credits": "MBTA/MassDOT GTFS, MassGIS, OpenStreetMap",
            "download_prefix": "boston-commute-cartogram",
            "url_label": "castrio.me/boston",
            "source_links": [
                {"label": "MBTA GTFS data", "url": "https://www.mbta.com/developers/gtfs", "emoji": "transit"},
                {"label": "MassGIS boundaries and open space", "url": "https://www.mass.gov/orgs/massgis-bureau-of-geographic-information", "emoji": "maps"},
                {"label": "OpenStreetMap streets", "url": "https://www.openstreetmap.org/", "emoji": "maps"},
            ],
        },
    },
}
```

- [ ] **Step 2: Add config access helpers**

Add these helpers below `LOCATION_CONFIGS`:

```python
def transit_config(config: dict) -> dict:
    return config["transit"]


def coverage_config(config: dict) -> dict:
    return config["coverage"]


def context_config(config: dict) -> dict:
    return config["context"]


def hooks_config(config: dict) -> dict:
    return config.get("hooks", {})


def ui_config(config: dict) -> dict:
    return config["ui"]
```

- [ ] **Step 3: Update argument choices**

Change:

```python
parser.add_argument("--city", choices=sorted(CITY_CONFIGS), default="nyc")
```

to:

```python
parser.add_argument("--city", choices=sorted(LOCATION_CONFIGS), default="nyc")
```

Change:

```python
config = CITY_CONFIGS[args.city]
```

to:

```python
config = LOCATION_CONFIGS[args.city]
```

- [ ] **Step 4: Update route filtering**

Replace `route_is_included` with:

```python
def route_is_included(row: dict, config: dict) -> bool:
    transit = transit_config(config)
    route_id = row.get("route_id")
    if route_id in transit.get("exclude_route_ids", set()):
        return False
    if route_id in transit.get("include_route_ids", set()):
        return True
    if row.get("route_type") in transit.get("include_route_types", set()):
        return True
    return False
```

- [ ] **Step 5: Update all direct config key reads**

Replace existing flat reads with nested reads:

```python
config["gtfs_path"] -> transit_config(config)["gtfs_path"]
config["station_source"] -> transit_config(config)["station_source"]
config["areas_path"] -> coverage_config(config)["areas_path"]
config["area_name_property"] -> coverage_config(config)["area_name_property"]
config.get("area_include_names") -> coverage_config(config).get("area_include_names")
config["parks_path"] -> context_config(config)["parks_path"]
config["park_area_property"] -> context_config(config)["park_area_property"]
config["park_area_min"] -> context_config(config)["park_area_min"]
config["streets_path"] -> context_config(config)["streets_path"]
config.get("external_land") -> context_config(config).get("external_land")
config["counties_kml_path"] -> context_config(config)["counties_kml_path"]
config.get("manual_connection") -> hooks_config(config).get("manual_connection")
config["search_query_suffix"] -> ui_config(config)["search_query_suffix"]
config["search_viewbox"] -> ui_config(config)["search_viewbox"]
config["share_text"] -> ui_config(config)["share_text"]
config["transit_note"] -> ui_config(config)["transit_note"]
config["data_credits"] -> ui_config(config)["data_credits"]
config["download_prefix"] -> ui_config(config)["download_prefix"]
config["url_label"] -> ui_config(config)["url_label"]
config["source_links"] -> ui_config(config)["source_links"]
```

In the output `meta` object, add:

```python
"transitNote": ui_config(config)["transit_note"],
"sourceLinks": ui_config(config)["source_links"],
```

- [ ] **Step 6: Syntax-check the builder**

Run:

```bash
python3 -m py_compile build_commute_site_data.py
```

Expected: no output and exit code 0.

- [ ] **Step 7: Rebuild and compare NYC/Boston**

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 scripts/compare_commute_data.py tmp/baselines/nyc.json site/data/nyc/commute_map_data.json
python3 scripts/compare_commute_data.py tmp/baselines/boston.json site/data/boston/commute_map_data.json
```

Expected: both comparisons print `commute data matches`.

- [ ] **Step 8: Commit**

Run:

```bash
git add build_commute_site_data.py
git commit -m "refactor: move city settings into location manifest"
```

## Task 4: Generalize Source Ensuring

**Files:**
- Modify: `build_commute_site_data.py`

- [ ] **Step 1: Replace Boston-only source ensure with generic functions**

Add:

```python
def ensure_static_gtfs(config: dict) -> None:
    transit = transit_config(config)
    gtfs_path = transit["gtfs_path"]
    gtfs_url = transit.get("gtfs_url")
    if gtfs_path.exists():
        return
    if not gtfs_url:
        raise FileNotFoundError(f"Missing GTFS file for {config['slug']}: {gtfs_path}")
    download_file(gtfs_url, gtfs_path)


def ensure_arcgis_coverage(config: dict) -> None:
    coverage = coverage_config(config)
    areas_path = coverage["areas_path"]
    if areas_path.exists():
        return
    areas_url = coverage.get("areas_url")
    if not areas_url:
        raise FileNotFoundError(f"Missing area file for {config['slug']}: {areas_path}")

    include_names = coverage.get("area_include_names")
    name_property = coverage["area_name_property"]
    where = "1=1"
    if include_names:
        quoted = "', '".join(sorted(include_names))
        where = f"{name_property} IN ('{quoted}')"

    payload = query_arcgis_geojson(
        areas_url,
        {
            "where": where,
            "outFields": "*",
            "outSR": 4326,
            "returnGeometry": "true",
        },
    )
    write_json(areas_path, payload)
```

- [ ] **Step 2: Add generic source ensure orchestration**

Add:

```python
def ensure_source_data(config: dict) -> None:
    ensure_static_gtfs(config)
    ensure_arcgis_coverage(config)
```

In `main`, replace:

```python
if config["slug"] == "boston":
    ensure_boston_source_data(config)
```

with:

```python
ensure_source_data(config)
```

- [ ] **Step 3: Keep Boston context fetch as the first generic context case**

Rename `ensure_boston_context_data` to `ensure_context_data` and make it return immediately unless the config has missing context files and source hooks. Preserve current Boston behavior for MassGIS parks and Overpass streets.

Use this guard at the top:

```python
def ensure_context_data(config: dict, bbox_lonlat: Tuple[float, float, float, float]) -> None:
    if config["slug"] != "boston":
        return
```

Then update the `main` call from `ensure_boston_context_data(...)` to `ensure_context_data(...)`.

- [ ] **Step 4: Rebuild and compare NYC/Boston**

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 scripts/compare_commute_data.py tmp/baselines/nyc.json site/data/nyc/commute_map_data.json
python3 scripts/compare_commute_data.py tmp/baselines/boston.json site/data/boston/commute_map_data.json
```

Expected: both comparisons print `commute data matches`.

- [ ] **Step 5: Commit**

Run:

```bash
git add build_commute_site_data.py
git commit -m "refactor: generalize source data setup"
```

## Task 5: Strengthen Generated Data Checks

**Files:**
- Modify: `scripts/check_commute_data.py`

- [ ] **Step 1: Add Chicago path and graph invariants**

Change `DATASETS` to:

```python
DATASETS = {
    "nyc": ROOT / "site" / "data" / "nyc" / "commute_map_data.json",
    "boston": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
    "chicago": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
}
```

In `main`, skip missing Chicago until it is generated:

```python
for city, path in DATASETS.items():
    if city == "chicago" and not path.exists():
        print("chicago: skipped; data not generated yet")
        continue
```

Add to `check_common` after length checks:

```python
    station_count = len(data["stations"])
    route_state_count = len(data["routeStates"])
    route_style_ids = set(data["routeStyles"])

    for index, route_state in enumerate(data["routeStates"]):
        station_index = route_state.get("stationIndex")
        route_id = route_state.get("routeId")
        require(isinstance(station_index, int) and 0 <= station_index < station_count, f"{city} routeState {index} invalid stationIndex")
        require(route_id in route_style_ids, f"{city} routeState {index} unknown routeId {route_id}")

    for station_index, state_indexes in enumerate(data["stationStates"]):
        require(isinstance(state_indexes, list), f"{city} stationStates[{station_index}] is not a list")
        for state_index in state_indexes:
            require(isinstance(state_index, int) and 0 <= state_index < route_state_count, f"{city} stationStates[{station_index}] invalid route state")

    for from_state, edges in enumerate(data["adjacency"]):
        require(isinstance(edges, list), f"{city} adjacency[{from_state}] is not a list")
        for edge in edges:
            require(isinstance(edge, list) and len(edge) == 2, f"{city} adjacency[{from_state}] invalid edge")
            to_state, weight = edge
            require(isinstance(to_state, int) and 0 <= to_state < route_state_count, f"{city} adjacency[{from_state}] invalid destination")
            require(isinstance(weight, (int, float)) and weight > 0, f"{city} adjacency[{from_state}] invalid weight")

    for station in data["stations"]:
        for route_id in station["routes"]:
            require(route_id in route_style_ids, f"{city} station {station.get('name')} has unknown route {route_id}")
```

- [ ] **Step 2: Add Chicago smoke check**

Add:

```python
CHICAGO_L_ROUTES = {"Red", "Blue", "Brn", "G", "Org", "Pink", "P", "Y"}


def check_chicago(data: dict) -> None:
    route_ids = set(data["routeStyles"])
    require(CHICAGO_L_ROUTES.issubset(route_ids), "chicago missing one or more CTA L routes")
    require(all(route_id in CHICAGO_L_ROUTES for route_id in route_ids), "chicago includes non-L route ids")
    station_names = {station.get("name") for station in data["stations"]}
    require("Clark/Lake" in station_names or "State/Lake" in station_names, "chicago missing expected Loop station")
```

In `main`, add:

```python
elif city == "chicago":
    check_chicago(data)
```

- [ ] **Step 3: Run checks before Chicago exists**

Run:

```bash
python3 scripts/check_commute_data.py
```

Expected output includes:

```text
nyc: ok
boston: ok
chicago: skipped; data not generated yet
```

- [ ] **Step 4: Commit**

Run:

```bash
git add scripts/check_commute_data.py
git commit -m "test: strengthen commute data invariants"
```

## Task 6: Add Chicago Builder Support

**Files:**
- Modify: `build_commute_site_data.py`
- Generated: `data/chicago/cta_gtfs.zip`
- Generated: `data/chicago/municipalities.geojson`
- Generated: `data/chicago/osm_major_streets.json`
- Generated: `site/data/chicago/commute_map_data.json`

- [ ] **Step 1: Add Chicago constants**

Add near the existing path constants:

```python
CHICAGO_DATA_DIR = DATA_DIR / "chicago"
CHICAGO_AREAS_PATH = CHICAGO_DATA_DIR / "municipalities.geojson"
CHICAGO_STREETS_PATH = CHICAGO_DATA_DIR / "osm_major_streets.json"
CHICAGO_GTFS_PATH = CHICAGO_DATA_DIR / "cta_gtfs.zip"
CHICAGO_CTA_GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"
CHICAGO_MUNICIPALITIES_URL = (
    "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/"
    "Cook_County_Municipalities/FeatureServer/0/query"
)
CHICAGO_MUNICIPALITIES = (
    "Chicago",
    "Cicero",
    "Evanston",
    "Forest Park",
    "Oak Park",
    "Rosemont",
    "Skokie",
    "Wilmette",
)
```

- [ ] **Step 2: Add Chicago manifest entry**

Add a `chicago` entry to `LOCATION_CONFIGS`:

```python
"chicago": {
    "slug": "chicago",
    "display_name": "Chicago",
    "short_name": "Chicago",
    "area_kind": "municipalities",
    "output_path": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
    "city_output_path": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
    "transit": {
        "gtfs_path": CHICAGO_GTFS_PATH,
        "gtfs_url": CHICAGO_CTA_GTFS_URL,
        "station_source": "gtfs_parent_stations",
        "include_route_types": {"1"},
        "include_route_ids": set(),
        "exclude_route_ids": set(),
        "service_policy": "CTA L only. Excludes CTA buses and Metra.",
    },
    "coverage": {
        "areas_path": CHICAGO_AREAS_PATH,
        "areas_url": CHICAGO_MUNICIPALITIES_URL,
        "area_name_property": "MUNICIPALITY",
        "area_include_names": set(CHICAGO_MUNICIPALITIES),
    },
    "context": {
        "parks_path": None,
        "park_area_property": None,
        "park_area_min": 70000.0,
        "streets_path": CHICAGO_STREETS_PATH,
    },
    "hooks": {
        "manual_connection": None,
    },
    "ui": {
        "search_query_suffix": "Chicago, Illinois",
        "search_viewbox": "-87.95,42.10,-87.45,41.55",
        "share_text": "Explore Chicago by CTA L commute time with this interactive transit cartogram.",
        "transit_note": (
            "Travel times are estimated from CTA GTFS rail trips plus short walking access to and "
            "from stations. The map includes CTA L service and excludes buses, Metra, and real-time schedules."
        ),
        "data_credits": "CTA GTFS, Cook County open data, OpenStreetMap",
        "download_prefix": "chicago-commute-cartogram",
        "url_label": "castrio.me/chicago",
        "source_links": [
            {"label": "CTA GTFS data", "url": "https://www.transitchicago.com/developers/gtfs/", "emoji": "transit"},
            {"label": "Cook County municipalities", "url": "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/Cook_County_Municipalities/FeatureServer", "emoji": "maps"},
            {"label": "OpenStreetMap streets", "url": "https://www.openstreetmap.org/", "emoji": "maps"},
        ],
    },
},
```

- [ ] **Step 3: Make optional parks safe**

In `extract_parks`, change the first lines to:

```python
def extract_parks(lat0: float, bbox: Tuple[float, float, float, float], config: dict) -> list:
    context = context_config(config)
    parks_path = context.get("parks_path")
    if not parks_path or not parks_path.exists():
        return []
```

Update property reads in that function to use `context`.

- [ ] **Step 4: Fetch Overpass streets for any city with missing streets**

Refactor the Overpass portion of `ensure_context_data` into:

```python
def ensure_overpass_major_streets(config: dict, bbox_lonlat: Tuple[float, float, float, float]) -> None:
    streets_path = context_config(config).get("streets_path")
    if not streets_path or streets_path.exists():
        return
    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    overpass_query = f"""
    [out:json][timeout:60];
    (
      way["highway"~"^(motorway|trunk|primary)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out tags geom;
    """
    query = urllib.parse.urlencode({"data": overpass_query}).encode("utf-8")
    request = urllib.request.Request(
        BOSTON_OVERPASS_URL,
        data=query,
        headers={"User-Agent": f"nyc-cartogram-{config['slug']}-data-builder/1.0"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            streets_path.parent.mkdir(parents=True, exist_ok=True)
            streets_path.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        print(f"Warning: could not fetch {config['slug']} OSM streets ({error}); continuing without streets.")
```

Call this from `ensure_context_data` for every city after any Boston-specific parks fetch:

```python
ensure_overpass_major_streets(config, bbox_lonlat)
```

- [ ] **Step 5: Build Chicago**

Run:

```bash
python3 build_commute_site_data.py --city chicago
```

Expected: it downloads missing Chicago sources and writes:

```text
Wrote /Users/samhitov/dev/codex/nyc-cartogram/site/data/chicago/commute_map_data.json
```

- [ ] **Step 6: Inspect Chicago route IDs if smoke check fails**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("site/data/chicago/commute_map_data.json").read_text())
print(sorted(data["routeStyles"]))
print(sorted(station["name"] for station in data["stations"] if "Lake" in station["name"])[:20])
PY
```

Expected route IDs should match CTA rail IDs. If CTA uses a different purple route ID than `P`, update `CHICAGO_L_ROUTES` in `scripts/check_commute_data.py` to the actual ID from the generated data.

- [ ] **Step 7: Run generated data checks**

Run:

```bash
python3 scripts/check_commute_data.py
```

Expected output includes:

```text
nyc: ok
boston: ok
chicago: ok
```

- [ ] **Step 8: Commit**

Run:

```bash
git add build_commute_site_data.py scripts/check_commute_data.py data/chicago site/data/chicago
git commit -m "feat: add Chicago commute data"
```

## Task 7: Add Chicago Frontend And Worker Routing

**Files:**
- Modify: `site/app.js`
- Modify: `site/index.html`
- Modify: `src/worker.js`

- [ ] **Step 1: Centralize frontend supported slugs**

At the top of `site/app.js`, add:

```javascript
const SUPPORTED_CITY_SLUGS = new Set(["nyc", "boston", "chicago"]);
```

Change `detectCitySlug` to:

```javascript
function detectCitySlug() {
  const params = new URLSearchParams(window.location.search);
  const queryCity = params.get("city");
  if (SUPPORTED_CITY_SLUGS.has(queryCity)) return queryCity;
  const firstPathSegment = window.location.pathname.split("/").filter(Boolean)[0];
  if (SUPPORTED_CITY_SLUGS.has(firstPathSegment)) return firstPathSegment;
  return "nyc";
}
```

- [ ] **Step 2: Add Chicago emoji fallback**

In `EMOJI_BURST_SETS`, add:

```javascript
chicago: ["🚇", "🏙️", "🌊", "⭐", "🚉"],
```

- [ ] **Step 3: Centralize HTML deploy slugs**

In `site/index.html`, replace the inline Boston/NYC detection script logic with:

```javascript
const supportedSlugs = new Set(["nyc", "boston", "chicago"]);
const firstSegment = path.split("/").filter(Boolean)[0];
const deploySlug = supportedSlugs.has(firstSegment) ? firstSegment : "nyc";
const isSubpathDeploy = supportedSlugs.has(firstSegment);
```

Keep the existing `assetBase` assignment after this replacement.

- [ ] **Step 4: Add IDs for dataset-driven note and source links**

In `site/index.html`, change:

```html
<section class="notes">
  <p>
```

to:

```html
<section class="notes">
  <p id="transitNote">
```

Change:

```html
<div class="footer-links">
```

to:

```html
<div id="sourceLinks" class="footer-links">
```

- [ ] **Step 5: Render dataset-driven note and source links**

Near the other DOM lookups in `site/app.js`, add:

```javascript
const transitNote = document.getElementById("transitNote");
const sourceLinks = document.getElementById("sourceLinks");
```

Add this function near `applyCityCopy`:

```javascript
function applyCitySources() {
  const meta = cityMeta();
  if (transitNote && meta.transitNote) {
    transitNote.textContent = `${meta.transitNote} Check out the `;
    const githubLink = document.createElement("a");
    githubLink.href = "https://github.com/AntCas/nyc-cartogram/tree/main";
    githubLink.target = "_blank";
    githubLink.rel = "noreferrer";
    githubLink.textContent = "GitHub";
    transitNote.appendChild(githubLink);
    transitNote.append(".");
  }
  if (sourceLinks && Array.isArray(meta.sourceLinks)) {
    sourceLinks.replaceChildren(
      ...meta.sourceLinks.map((source) => {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.dataset.emojiBurst = source.emoji || "maps";
        link.textContent = source.label;
        return link;
      }),
    );
  }
}
```

In `init`, after `applyCityCopy();`, add:

```javascript
applyCitySources();
```

- [ ] **Step 6: Add Chicago worker prefix**

In `src/worker.js`, change:

```javascript
const PATH_PREFIXES = ["/nyc", "/boston"];
```

to:

```javascript
const PATH_PREFIXES = ["/nyc", "/boston", "/chicago"];
```

- [ ] **Step 7: Run JavaScript syntax checks**

Run:

```bash
npm run check:js
```

Expected: no syntax errors.

- [ ] **Step 8: Commit**

Run:

```bash
git add site/app.js site/index.html src/worker.js
git commit -m "feat: route Chicago frontend assets"
```

## Task 8: Final Verification

**Files:**
- Read: `TESTING.md`
- Generated: `site/data/nyc/commute_map_data.json`
- Generated: `site/data/boston/commute_map_data.json`
- Generated: `site/data/chicago/commute_map_data.json`

- [ ] **Step 1: Rebuild all supported cities**

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 build_commute_site_data.py --city chicago
```

Expected: all three commands write their city data.

- [ ] **Step 2: Run data checks**

Run:

```bash
python3 scripts/check_commute_data.py
```

Expected:

```text
nyc: ok
boston: ok
chicago: ok
```

- [ ] **Step 3: Run project checks**

Run:

```bash
npm run check
```

Expected: data checks and JS syntax checks pass.

- [ ] **Step 4: Compare preserved cities one last time**

Run:

```bash
python3 scripts/compare_commute_data.py tmp/baselines/nyc.json site/data/nyc/commute_map_data.json
python3 scripts/compare_commute_data.py tmp/baselines/boston.json site/data/boston/commute_map_data.json
```

Expected: both comparisons print `commute data matches`. If they do not match after Chicago-only changes, inspect the diff source before finishing.

- [ ] **Step 5: Summarize remaining manual browser checks**

Open a static server:

```bash
python3 -m http.server 8000
```

Check:

```text
http://localhost:8000/site/?city=nyc
http://localhost:8000/site/?city=boston
http://localhost:8000/site/?city=chicago
```

Expected: each city loads, displays its map, search placeholder uses the city name, and pinning an origin computes commute times.

- [ ] **Step 6: Final commit if generated data or docs remain uncommitted**

Run:

```bash
git status --short
```

Commit only intentional source, data, and documentation changes. Do not commit `tmp/baselines/`.
