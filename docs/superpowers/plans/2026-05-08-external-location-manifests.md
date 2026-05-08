# External Location Manifests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move location manifests out of `build_commute_site_data.py` into `locations/*.json`, generate a frontend location registry from those manifests, and add checks that prevent builder/frontend/Worker route drift.

**Architecture:** Keep the current build pipeline behavior, but replace the in-file `LOCATION_CONFIGS` literal with a JSON manifest loader that returns the same runtime shape. Add `site/data/locations.json` generation from manifests, make `site/app.js` load that registry before city data, and validate manifests, Worker prefixes, and Wrangler routes in a new checker.

**Tech Stack:** Python 3 standard library, JSON manifests, static JavaScript, Cloudflare Worker config.

---

## File Map

- Create `locations/nyc.json`, `locations/boston.json`, `locations/chicago.json`, `locations/philadelphia.json`, `locations/montreal.json`.
- Create `locations/README.md`.
- Create `docs/ADDING_LOCATION.md`.
- Create `scripts/check_location_manifests.py`.
- Modify `build_commute_site_data.py` to load manifests and generate `site/data/locations.json`.
- Modify `site/app.js` to load the registry instead of hardcoding city slugs and city emoji sets.
- Modify `package.json` to run the manifest check.
- Modify `scripts/check_commute_data.py` only if generated registry validation needs to be included in data checks.
- Generated and committed: `site/data/locations.json`.

## Task 1: Document Location Manifests And Add-Location Workflow

**Files:**
- Create: `locations/README.md`
- Create: `docs/ADDING_LOCATION.md`

- [ ] **Step 1: Create `locations/README.md`**

Add a manifest schema guide with these sections:

```markdown
# Location Manifests

Each `locations/<slug>.json` file describes one supported commute cartogram location.
The builder loads these manifests and turns them into runtime configuration.

## Required Top-Level Fields

- `slug`: URL/data slug. Must match the filename stem.
- `displayName`: Full UI name.
- `areaKind`: Label for displayed administrative areas.
- `outputPath`: Primary generated data path.
- `cityOutputPath`: City-specific generated data path.
- `transit`: GTFS and route policy.
- `coverage`: labeled areas and broader land mask sources.
- `context`: optional parks and streets sources.
- `ui`: search, sharing, download, and source metadata.

`shortName` is optional. If omitted, it defaults to `displayName`.

## Transit Policy

Include fixed-stop urban transit that is not generally affected by car traffic.
Exclude ordinary mixed-traffic buses and commuter/regional rail.
Do not rely only on GTFS `route_type` after initial inspection. Route allowlists must be explicit.

## Coverage Policy

`areasPath` is for labeled/display areas.
`landAreasPath` is for broader land coverage used to decide land versus water.
Do not use labeled areas as the land mask unless they cover all nearby land in the map extent.
For non-NYC locations, `landAreasPath` is required.

## Optional Hooks

Hooks are exceptional. Use them only when data cannot be represented declaratively, such as NYC's Staten Island Ferry manual connection.

## Optional UI Fields

`ui.emojiBurst` is optional. If omitted, the frontend uses a generic city/transit emoji fallback.
```

- [ ] **Step 2: Create `docs/ADDING_LOCATION.md`**

Add an agent workflow with this checklist:

```markdown
# Adding A Location

1. Find an official or public static GTFS source.
2. Add a draft `locations/<slug>.json`.
3. Use broad route filters only for the first inspection build.
4. Build once and inspect `routeStyles`.
5. Replace broad filters with explicit `includeRouteIds`.
6. Choose labeled areas separately from broader land-mask areas.
7. Add smoke checks for:
   - expected route IDs;
   - unwanted bus or commuter/regional routes absent;
   - a central station;
   - an unlabeled nearby land point inside `landMask`.
8. Add Worker and Wrangler route entries when the city should be deployable.
9. Run `npm run check`.
10. Commit one city at a time.

Stop and report if GTFS access is gated behind authentication.
Do not include commuter rail or ordinary mixed-traffic buses unless the project policy changes.
Do not treat unlabeled municipalities as water.
```

- [ ] **Step 3: Commit documentation**

Run:

```bash
git add locations/README.md docs/ADDING_LOCATION.md
git commit -m "docs: document location manifest workflow"
```

## Task 2: Extract JSON Manifests

**Files:**
- Create: `locations/nyc.json`
- Create: `locations/boston.json`
- Create: `locations/chicago.json`
- Create: `locations/philadelphia.json`
- Create: `locations/montreal.json`

- [ ] **Step 1: Create the `locations` directory**

Run:

```bash
mkdir -p locations
```

- [ ] **Step 2: Create `locations/nyc.json`**

Use the current `LOCATION_CONFIGS["nyc"]` values. Convert snake_case keys to camelCase JSON keys. Convert paths to repository-relative strings. Convert sets to arrays.

The file must include:

```json
{
  "slug": "nyc",
  "displayName": "New York City",
  "shortName": "NYC",
  "areaKind": "boroughs",
  "outputPath": "site/data/commute_map_data.json",
  "cityOutputPath": "site/data/nyc/commute_map_data.json",
  "transit": {
    "gtfsPath": "data/mta_gtfs_subway.zip",
    "stationSource": "nyc_station_json",
    "includeRouteTypes": ["1"],
    "includeRouteIds": ["SI"],
    "excludeRouteIds": []
  },
  "coverage": {
    "areasPath": "data/borough_boundaries.geojson",
    "areaNameProperty": "boroname",
    "landAreasPath": null
  },
  "context": {
    "parksPath": "data/parks_open_space.geojson",
    "parkAreaProperty": "shape_area",
    "parkAreaMin": 70000.0,
    "streetsPath": "data/osm_major_streets.json",
    "externalLand": "nyc_counties",
    "countiesKmlPath": "data/cb_2024_us_county_500k.zip"
  },
  "hooks": {
    "manualConnection": "staten_island_ferry"
  },
  "ui": {
    "searchQuerySuffix": "New York City",
    "searchViewbox": "-74.30,40.95,-73.65,40.45",
    "shareText": "Explore New York City by subway commute time with this interactive transit cartogram.",
    "dataCredits": "MTA GTFS, NYC Open Data, OpenStreetMap",
    "downloadPrefix": "nyc-commute-cartogram",
    "urlLabel": "castrio.me/nyc",
    "emojiBurst": ["🗽", "🌆", "🏙️", "🚕", "🍎"]
  }
}
```

- [ ] **Step 3: Create the other current manifests**

Create `boston`, `chicago`, `philadelphia`, and `montreal` JSON files using the same conversion rules:

- `gtfs_member` becomes `gtfsMember`.
- `area_include_names` becomes `areaIncludeNames`.
- `land_include_names` becomes `landIncludeNames`.
- `city_output_path` becomes `cityOutputPath`.
- `manual_connection` becomes `manualConnection`.
- missing optional fields should be omitted unless they are explicitly `null` in the NYC example.
- `shortName` may be omitted when it would equal `displayName`; the loader will default it.
- `ui.emojiBurst` may be omitted; the frontend will use a generic fallback.

Use these route allowlists:

```json
["Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E", "Mattapan"]
```

```json
["Red", "Blue", "Brn", "G", "Org", "Pink", "P", "Y"]
```

```json
["B1", "B2", "B3", "D1", "D2", "G1", "L1", "M1", "T1", "T2", "T3", "T4", "T5"]
```

```json
["1", "2", "4", "5"]
```

- [ ] **Step 4: Commit manifests**

Run:

```bash
git add locations
git commit -m "config: extract location manifests"
```

## Task 3: Add Manifest Loader

**Files:**
- Modify: `build_commute_site_data.py`

- [ ] **Step 1: Add loader helpers**

Add imports:

```python
from copy import deepcopy
```

Add constants:

```python
LOCATIONS_DIR = ROOT / "locations"
FRONTEND_LOCATIONS_PATH = ROOT / "site" / "data" / "locations.json"
```

Add helper functions near the existing config helpers:

```python
def resolve_repo_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = ROOT / value
    resolved = path.resolve()
    if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
        raise ValueError(f"Manifest path escapes repository: {value}")
    return path


def normalize_manifest(raw: dict) -> dict:
    config = {
        "slug": raw["slug"],
        "display_name": raw["displayName"],
        "short_name": raw.get("shortName", raw["displayName"]),
        "area_kind": raw["areaKind"],
        "output_path": resolve_repo_path(raw["outputPath"]),
        "city_output_path": resolve_repo_path(raw["cityOutputPath"]),
        "transit": deepcopy(raw["transit"]),
        "coverage": deepcopy(raw["coverage"]),
        "context": deepcopy(raw["context"]),
        "hooks": deepcopy(raw.get("hooks", {})),
        "ui": deepcopy(raw["ui"]),
    }
    transit = config["transit"]
    transit["gtfs_path"] = resolve_repo_path(transit.pop("gtfsPath"))
    if "gtfsUrl" in transit:
        transit["gtfs_url"] = transit.pop("gtfsUrl")
    if "gtfsMember" in transit:
        transit["gtfs_member"] = transit.pop("gtfsMember")
    transit["station_source"] = transit.pop("stationSource")
    transit["include_route_types"] = set(transit.pop("includeRouteTypes", []))
    transit["include_route_ids"] = set(transit.pop("includeRouteIds", []))
    transit["exclude_route_ids"] = set(transit.pop("excludeRouteIds", []))
    if "servicePolicy" in transit:
        transit["service_policy"] = transit.pop("servicePolicy")

    coverage = config["coverage"]
    coverage["areas_path"] = resolve_repo_path(coverage.pop("areasPath"))
    if "areasUrl" in coverage:
        coverage["areas_url"] = coverage.pop("areasUrl")
    coverage["area_name_property"] = coverage.pop("areaNameProperty")
    if "areaIncludeNames" in coverage:
        coverage["area_include_names"] = set(coverage.pop("areaIncludeNames"))
    if "landAreasPath" in coverage:
        coverage["land_areas_path"] = resolve_repo_path(coverage.pop("landAreasPath"))
    if "landAreasUrl" in coverage:
        coverage["land_areas_url"] = coverage.pop("landAreasUrl")
    if "landWhere" in coverage:
        coverage["land_where"] = coverage.pop("landWhere")
    if "landIncludeNames" in coverage:
        coverage["land_include_names"] = set(coverage.pop("landIncludeNames"))

    context = config["context"]
    for key, snake in (
        ("parksPath", "parks_path"),
        ("streetsPath", "streets_path"),
        ("countiesKmlPath", "counties_kml_path"),
    ):
        if key in context:
            context[snake] = resolve_repo_path(context.pop(key))
    if "parkAreaProperty" in context:
        context["park_area_property"] = context.pop("parkAreaProperty")
    if "parkAreaMin" in context:
        context["park_area_min"] = context.pop("parkAreaMin")
    if "externalLand" in context:
        context["external_land"] = context.pop("externalLand")

    hooks = config["hooks"]
    if "manualConnection" in hooks:
        hooks["manual_connection"] = hooks.pop("manualConnection")

    ui = config["ui"]
    for key, snake in (
        ("searchQuerySuffix", "search_query_suffix"),
        ("searchViewbox", "search_viewbox"),
        ("shareText", "share_text"),
        ("dataCredits", "data_credits"),
        ("downloadPrefix", "download_prefix"),
        ("urlLabel", "url_label"),
        ("emojiBurst", "emoji_burst"),
    ):
        if key in ui:
            ui[snake] = ui.pop(key)

    return config


def load_location_configs() -> dict:
    configs = {}
    for path in sorted(LOCATIONS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = normalize_manifest(raw)
        if path.stem != config["slug"]:
            raise ValueError(f"Manifest filename {path.name} does not match slug {config['slug']}")
        configs[config["slug"]] = config
    if "nyc" not in configs:
        raise ValueError("Missing default nyc location manifest")
    return configs
```

- [ ] **Step 2: Replace the in-file manifest**

Remove the existing `LOCATION_CONFIGS = { ... }` literal and set:

```python
LOCATION_CONFIGS = load_location_configs()
```

Keep constants that are still used outside manifests, such as numeric travel constants and Staten Island Ferry constants.

- [ ] **Step 3: Syntax-check**

Run:

```bash
python3 -m py_compile build_commute_site_data.py
```

Expected: no output and exit 0.

- [ ] **Step 4: Rebuild a small sample**

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city chicago
python3 scripts/check_commute_data.py
```

Expected: generated data checks pass.

- [ ] **Step 5: Commit loader**

Run:

```bash
git add build_commute_site_data.py site/data/commute_map_data.json site/data/nyc/commute_map_data.json site/data/chicago/commute_map_data.json
git commit -m "refactor: load location manifests from json"
```

## Task 4: Generate Frontend Location Registry

**Files:**
- Modify: `build_commute_site_data.py`
- Create/Generate: `site/data/locations.json`

- [ ] **Step 1: Add registry generator**

Add:

```python
def city_data_url(config: dict) -> str:
    return f"./data/{config['slug']}/commute_map_data.json"


def build_frontend_location_registry(configs: dict) -> dict:
    cities = []
    for slug, config in sorted(configs.items()):
        ui = ui_config(config)
        cities.append(
            {
                "slug": slug,
                "displayName": config["display_name"],
                "shortName": config["short_name"],
                "dataUrl": city_data_url(config),
                "urlLabel": ui["url_label"],
                **({"emojiBurst": ui["emoji_burst"]} if ui.get("emoji_burst") else {}),
            }
        )
    return {"defaultSlug": "nyc", "cities": cities}


def write_frontend_location_registry(configs: dict) -> None:
    FRONTEND_LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_LOCATIONS_PATH.write_text(
        json.dumps(build_frontend_location_registry(configs), separators=(",", ":")),
        encoding="utf-8",
    )
```

Call `write_frontend_location_registry(LOCATION_CONFIGS)` in `main()` before writing city output.

- [ ] **Step 2: Build one city to generate registry**

Run:

```bash
python3 build_commute_site_data.py --city chicago
python3 -m json.tool site/data/locations.json
```

Expected: registry includes `nyc`, `boston`, `chicago`, `philadelphia`, and `montreal`.

- [ ] **Step 3: Commit registry generator**

Run:

```bash
git add build_commute_site_data.py site/data/locations.json site/data/chicago/commute_map_data.json
git commit -m "feat: generate frontend location registry"
```

## Task 5: Make `site/app.js` Registry-Driven

**Files:**
- Modify: `site/app.js`

- [ ] **Step 1: Replace hardcoded city slug set**

Remove:

```javascript
const SUPPORTED_CITY_SLUGS = new Set([...]);
const CITY_SLUG = detectCitySlug();
const DATA_URL = new URL(`./data/${CITY_SLUG}/commute_map_data.json`, import.meta.url).toString();
```

Add:

```javascript
let locationRegistry = null;
let currentLocation = null;
let CITY_SLUG = "nyc";
let DATA_URL = "";
```

- [ ] **Step 2: Add registry loading and city detection**

Replace `detectCitySlug()` with:

```javascript
async function loadLocationRegistry() {
  const registryUrl = new URL("./data/locations.json", import.meta.url).toString();
  const response = await fetch(registryUrl);
  return response.json();
}

function detectCitySlug(registry) {
  const supportedSlugs = new Set(registry.cities.map((city) => city.slug));
  const params = new URLSearchParams(window.location.search);
  const queryCity = params.get("city");
  if (supportedSlugs.has(queryCity)) return queryCity;
  const firstPathSegment = window.location.pathname.split("/").filter(Boolean)[0];
  if (supportedSlugs.has(firstPathSegment)) return firstPathSegment;
  return registry.defaultSlug || "nyc";
}

function selectCurrentLocation(registry) {
  const slug = detectCitySlug(registry);
  return registry.cities.find((city) => city.slug === slug) || registry.cities[0];
}
```

- [ ] **Step 3: Update `init()`**

At the start of `init()`, before fetching city data, add:

```javascript
locationRegistry = await loadLocationRegistry();
currentLocation = selectCurrentLocation(locationRegistry);
CITY_SLUG = currentLocation.slug;
DATA_URL = new URL(currentLocation.dataUrl, import.meta.url).toString();
```

Then fetch `DATA_URL` as before.

- [ ] **Step 4: Move city emoji to registry**

Remove city-specific entries from `EMOJI_BURST_SETS`: `nyc`, `chicago`, `philadelphia`, `montreal`.

Add:

```javascript
const DEFAULT_CITY_EMOJI_BURST = ["🚇", "🏙️", "🚉", "📍", "🗺️"];

function emojiBurstSet(theme) {
  if (theme === "city") return currentLocation?.emojiBurst?.length ? currentLocation.emojiBurst : DEFAULT_CITY_EMOJI_BURST;
  return EMOJI_BURST_SETS[theme] || EMOJI_BURST_SETS.maps;
}
```

Change `emitEmojiBurst` from:

```javascript
const emojis = EMOJI_BURST_SETS[theme];
```

to:

```javascript
const emojis = emojiBurstSet(theme);
```

- [ ] **Step 5: Run frontend checks**

Run:

```bash
npm run check:js
python3 scripts/check_frontend_landmask.py
```

Expected: both pass.

- [ ] **Step 6: Commit app refactor**

Run:

```bash
git add site/app.js
git commit -m "refactor: load frontend locations from registry"
```

## Task 6: Add Manifest Consistency Checker

**Files:**
- Create: `scripts/check_location_manifests.py`
- Modify: `package.json`

- [ ] **Step 1: Create checker**

Create `scripts/check_location_manifests.py` that:

- loads every `locations/*.json`;
- validates required top-level keys;
- validates `shortName` is optional and defaults via loader rather than being required;
- validates `ui.emojiBurst` is optional, but if present it is a list of strings;
- validates filename stem equals `slug`;
- validates route fields are lists of strings;
- validates relative paths do not escape repo;
- loads `src/worker.js` and checks every manifest slug appears as `"/<slug>"`;
- loads `wrangler.jsonc` as JSON and checks every manifest slug has `castrio.me/<slug>*`;
- loads `site/data/locations.json` if present and checks registry slugs match manifest slugs.
- error messages for land-mask, route-policy, and path-shape rules should point to `locations/README.md` or `docs/ADDING_LOCATION.md`.

- [ ] **Step 2: Add package script**

Update `package.json`:

```json
"check:manifests": "python3 scripts/check_location_manifests.py"
```

Update `check` to:

```json
"check": "npm run check:manifests && npm run check:data && npm run check:frontend-landmask && npm run check:js"
```

- [ ] **Step 3: Run checker**

Run:

```bash
python3 scripts/check_location_manifests.py
npm run check
```

Expected: all checks pass.

- [ ] **Step 4: Commit checker**

Run:

```bash
git add scripts/check_location_manifests.py package.json
git commit -m "test: validate location manifest consistency"
```

## Task 7: Final Rebuild And Verification

**Files:**
- Generated: `site/data/locations.json`
- Generated: city data files for supported cities.

- [ ] **Step 1: Rebuild all supported cities**

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 build_commute_site_data.py --city chicago
python3 build_commute_site_data.py --city philadelphia
python3 build_commute_site_data.py --city montreal
```

- [ ] **Step 2: Run full check**

Run:

```bash
npm run check
```

Expected: all checks pass.

- [ ] **Step 3: Review generated diffs**

Run:

```bash
git status --short
git diff --stat
```

Expected: no unexpected generated data churn beyond `site/data/locations.json`.

- [ ] **Step 4: Commit final generated registry/data if needed**

Run:

```bash
git add site/data/locations.json site/data/commute_map_data.json site/data/nyc/commute_map_data.json site/data/boston/commute_map_data.json site/data/chicago/commute_map_data.json site/data/philadelphia/commute_map_data.json site/data/montreal/commute_map_data.json
git commit -m "chore: refresh generated data from external manifests"
```

Only commit this if Step 3 shows generated changes.
