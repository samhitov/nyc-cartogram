# Multi-Location Manifest And Chicago Design

## Goal

Extend the commute cartogram codebase from NYC and Boston to a reusable multi-location system, then add Chicago as the next city. The refactor must preserve existing NYC and Boston generated output before adding Chicago.

## Scope

In scope:

- Move city-specific builder configuration into a reusable location manifest shape.
- Keep NYC and Boston behavior unchanged after the refactor.
- Add Chicago as the first new manifest-driven city.
- Include fixed-stop urban transit that is not generally affected by car traffic.
- Exclude ordinary mixed-traffic buses and longer commuter/regional rail.
- Keep London out of this phase because its data path is more complex.

Out of scope:

- Adding DC, Philly, Toronto, Montreal, Vancouver, or London in this implementation.
- Modeling real-time schedules.
- Adding commuter rail.
- Making a visual city picker or new landing page.

## Transit Policy

The default inclusion policy is:

- Include subway, metro, elevated rail, light rail, streetcar, and ferry when they function as fixed-stop urban transit.
- Exclude ordinary buses because they are generally affected by car traffic.
- Exclude commuter/regional rail for now.
- Allow each city to override route inclusion with explicit GTFS route IDs and exclusions.

For Chicago, include CTA `L` service only. Exclude CTA buses and Metra.

## Manifest Design

The manifest should describe location policy, source files, metadata, and validation expectations. Builder functions should consume this manifest instead of checking city slugs directly where a generic concept is available.

Each location config should include:

- `slug`, `display_name`, `short_name`.
- Output paths under `site/data/<slug>/commute_map_data.json`.
- Transit source information: GTFS path, optional download URL, station source, route type filters, explicit route allowlist, explicit route denylist, and a short service policy note.
- Coverage source information: area GeoJSON path, area name property, include-name list, and area kind label.
- Context source information: parks path/options and streets path/options.
- Search/UI metadata: search suffix, viewbox, share text, data credits, download prefix, URL label.
- Optional city-specific hooks only when a behavior is truly unique, such as NYC's Staten Island Ferry connection or external county land.

Example shape:

```python
LOCATION_CONFIGS = {
    "chicago": {
        "slug": "chicago",
        "display_name": "Chicago",
        "short_name": "Chicago",
        "area_kind": "municipalities",
        "output_path": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
        "transit": {
            "gtfs_path": DATA_DIR / "chicago" / "cta_gtfs.zip",
            "gtfs_url": "https://www.transitchicago.com/downloads/sch_data/google_transit.zip",
            "station_source": "gtfs_parent_stations",
            "include_route_types": {"1"},
            "include_route_ids": set(),
            "exclude_route_ids": set(),
            "service_policy": "CTA L only. Excludes CTA buses and Metra.",
        },
        "coverage": {
            "areas_path": DATA_DIR / "chicago" / "municipalities.geojson",
            "areas_url": "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/Cook_County_Municipalities/FeatureServer/0/query",
            "area_name_property": "MUNICIPALITY",
            "area_include_names": {
                "Chicago",
                "Cicero",
                "Evanston",
                "Forest Park",
                "Oak Park",
                "Rosemont",
                "Skokie",
                "Wilmette",
            },
        },
        "context": {
            "parks_path": None,
            "park_area_property": None,
            "park_area_min": 70000.0,
            "streets_path": DATA_DIR / "chicago" / "osm_major_streets.json",
        },
        "ui": {
            "search_query_suffix": "Chicago, Illinois",
            "search_viewbox": "-87.95,42.10,-87.45,41.55",
            "share_text": "Explore Chicago by CTA L commute time with this interactive transit cartogram.",
            "data_credits": "CTA GTFS, local open data, OpenStreetMap",
            "download_prefix": "chicago-commute-cartogram",
            "url_label": "castrio.me/chicago",
        },
    },
}
```

The implementation should verify the Cook County municipality name field against the fetched payload. If the field is named differently, update the manifest and keep the include-name policy unchanged.

## Builder Architecture

The builder should remain a standard-library Python script.

Refactor targets:

- Rename `CITY_CONFIGS` to a clearer manifest name such as `LOCATION_CONFIGS`.
- Normalize existing NYC and Boston config to the new nested shape.
- Replace `route_filter` with generic route inclusion logic:
  - include if `route_id` is in `include_route_ids`;
  - include if `route_type` is in `include_route_types`;
  - exclude if `route_id` is in `exclude_route_ids`;
  - otherwise exclude.
- Replace Boston-specific source ensuring with manifest-driven source hooks for static GTFS downloads, ArcGIS GeoJSON coverage downloads, and Overpass major-street downloads.
- Keep unique behaviors explicit and isolated, including NYC station JSON and Staten Island Ferry.
- Keep generated JSON schema compatible with the frontend.

Data download/fetch behavior should remain conservative. If a local source file already exists, reuse it. If a configured source file is missing and has a known static URL, download it. Context layers such as parks and streets may be empty if a fetch fails, but missing GTFS or coverage data should fail the build.

## Frontend And Worker

The frontend currently detects only `nyc` and `boston`. Update it so supported slugs are declared in one small list or generated metadata constant, then add `chicago`.

The Worker currently has a fixed `PATH_PREFIXES` list. Add `/chicago` for this phase. A larger city picker or index page is out of scope.

The existing HTML copy has NYC-specific notes and footer links. In this phase, update the visible transit note and footer data-source links to derive from dataset metadata after data load. Static social metadata can remain NYC-oriented until a later sharing-polish pass.

## Verification

Use exact golden-output comparison for the refactor, then invariant checks for ongoing development.

Before refactoring:

1. Build NYC and Boston data with the current code.
2. Save the generated files under a temporary baseline directory outside committed source, such as `tmp/baselines/`.

After refactoring:

1. Rebuild NYC and Boston.
2. Compare normalized JSON against the baselines.
3. Investigate any diff before adding Chicago.

The long-term test suite should continue to use invariant checks rather than committed full snapshots because upstream transit/source data can change. Expand `scripts/check_commute_data.py` so it validates every configured city and verifies:

- metadata exists and matches the city slug;
- required top-level arrays/maps exist and are non-empty;
- mask length matches grid dimensions;
- route states reference valid stations;
- station states reference valid route states;
- adjacency edges reference valid route states;
- every station route exists in `routeStyles`;
- city-specific smoke checks pass.

Chicago smoke checks should include at least:

- CTA rail routes are present;
- bus routes are absent;
- a central station such as Clark/Lake or State/Lake is present, subject to actual GTFS station naming.

Run:

```bash
python3 build_commute_site_data.py --city nyc
python3 build_commute_site_data.py --city boston
python3 scripts/check_commute_data.py
npm run check:js
```

After Chicago is added, also run:

```bash
python3 build_commute_site_data.py --city chicago
python3 scripts/check_commute_data.py
```

## Risks

- GTFS route types are not enough to encode the transit policy, so every new city needs a route review.
- Coverage polygons are the highest-risk source choice for Chicago because the app expects metro-area land covered by rapid transit, not just the main city boundary.
- Parent-station handling may need small corrections for agencies that do not model stations cleanly in GTFS.
- Static HTML metadata and footer links are still NYC-biased and may need a later cleanup for sharing polish.

## Chicago Source Decisions

Use CTA's official static GTFS ZIP for transit schedules. Use Cook County's municipality ArcGIS FeatureServer for coverage polygons, filtered to Chicago plus Cook County municipalities with CTA rail stations: Cicero, Evanston, Forest Park, Oak Park, Rosemont, Skokie, and Wilmette. Use Overpass major streets for the context street layer. Leave Chicago parks empty in this phase unless a simple metro-area park polygon source is already available locally.
