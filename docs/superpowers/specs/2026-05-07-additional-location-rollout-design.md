# Additional Location Rollout Design

## Goal

Add Philadelphia, Montreal, Toronto, Vancouver, and DC as manifest-driven commute cartogram locations, preserving the fixed-stop urban transit policy and the separate labeled-area versus land-mask model.

## Scope

In scope:

- Add locations one at a time in this order: Philadelphia, Montreal, Toronto, Vancouver, DC.
- Keep each location in a separate commit with generated data and smoke checks.
- Use static GTFS only.
- Include fixed-stop urban transit that is not generally affected by car traffic.
- Exclude ordinary mixed-traffic buses and commuter/regional rail.
- Use labeled `areas` for visible municipal labels and broader `landMask` polygons for land versus water treatment.
- Add frontend and Worker routing for every successfully generated city.

Out of scope:

- Real-time data.
- A visual city picker or landing page.
- Commuter/regional rail.
- Ordinary mixed-traffic bus service.
- Using private credentials for DC unless the WMATA GTFS feed blocks unauthenticated access and the user provides a key.

## Source Order And Risk

1. Philadelphia
   - Transit: SEPTA static GTFS from SEPTA's developer download or SEPTA's public GTFS GitHub release.
   - Transit policy: rapid transit only. Include Market-Frankford Line, Broad Street Line, Norristown High Speed Line, and trolley/subway-surface routes if GTFS route review confirms they behave like fixed-stop urban rail. Exclude Regional Rail and ordinary buses.
   - Land coverage: municipal/county polygons around the rapid-transit extent.

2. Montreal
   - Transit: STM planned GTFS at `https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip`.
   - Transit policy: Metro only. Exclude STM buses.
   - Land coverage: Montreal, Laval, Longueuil, and nearby unlabeled municipalities within the metro map extent.

3. Toronto
   - Transit: TTC static GTFS from Toronto Open Data.
   - Transit policy: subway/rapid transit only for the first pass. Exclude buses. Streetcars remain excluded unless a later policy decision includes street-running fixed rail.
   - Land coverage: Toronto plus adjacent GTA municipalities in the subway map extent.

4. Vancouver
   - Transit: TransLink static GTFS at `https://gtfs-static.translink.ca/gtfs/google_transit.zip`.
   - Transit policy: SkyTrain plus SeaBus if represented cleanly in GTFS. Exclude ordinary buses and West Coast Express.
   - Land coverage: Metro Vancouver municipalities in the rapid-transit map extent.
   - Attribution: include TransLink's required attribution language in data credits/source links.

5. DC
   - Transit: WMATA Rail GTFS. WMATA's official GTFS access is through its API portal and may require an `api_key` header.
   - Transit policy: Metrorail only. Exclude Metrobus and commuter rail.
   - Land coverage: DC plus adjacent Maryland and Virginia counties/cities in the Metrorail map extent.
   - If unauthenticated GTFS download fails, stop DC and report that a WMATA API key is required instead of blocking the other cities.

## Manifest Requirements

Each new location must define:

- `slug`, `display_name`, `short_name`, `area_kind`.
- `output_path` and `city_output_path` under `site/data/<slug>/commute_map_data.json`.
- `transit.gtfs_path`, optional `transit.gtfs_url`, `station_source`, route inclusion filters, and `service_policy`.
- `coverage.areas_path`, `coverage.areas_url` or local file source, `area_name_property`, and `area_include_names`.
- `coverage.land_areas_path` and a broader land source.
- `context.streets_path` for Overpass major-street context.
- `ui` metadata for search, sharing, data credits, download prefix, URL label, transit note, and source links.

## Validation

The checker should validate every successfully added city:

- Common graph invariants still pass.
- The city has non-empty `landMask`, except NYC which still uses `externalLand`.
- Route IDs match the reviewed fixed-stop urban transit set.
- Bus and commuter/regional route IDs are absent.
- At least one central station is present.
- At least one known adjacent, unlabeled municipality point is inside `landMask`.

Run after each city:

```bash
python3 build_commute_site_data.py --city <slug>
python3 scripts/check_commute_data.py
npm run check:js
```

Run after the full successful set:

```bash
npm run check
```

## Risks

- GTFS route types are not enough to encode local policy; every city needs route ID inspection.
- Canadian municipal boundary sources may not share a common ArcGIS shape and may need city-specific source URLs.
- DC may require a WMATA API key for static GTFS.
- Generated datasets may be large. Keep commits city-by-city so size and behavior changes are reviewable.
