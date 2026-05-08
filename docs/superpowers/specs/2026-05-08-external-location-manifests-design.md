# External Location Manifests Design

## Goal

Move location configuration out of `build_commute_site_data.py` into one declarative manifest file per location, then generate frontend and Worker-facing location registries from the same source of truth.

## Motivation

The current branch is manifest-driven in structure but not in storage: `LOCATION_CONFIGS` is a large Python dictionary inside the builder. That worked for the first few locations, but it will not scale cleanly to 20+ locations. The builder should describe the build algorithm, while location manifests should describe city-specific data sources, route policies, land coverage, and UI metadata.

## Architecture

Use one JSON manifest per location:

```text
locations/
  nyc.json
  boston.json
  chicago.json
  philadelphia.json
  montreal.json
```

The builder loads every manifest, validates required fields, resolves relative paths against the repository root, and exposes a `LOCATION_CONFIGS` mapping with the same runtime shape currently used by the build pipeline.

Rare location-specific code stays in Python hooks:

```text
location_hooks/
  __init__.py
  nyc.py
```

Hooks are referenced by name from JSON, for example:

```json
"hooks": {
  "manualConnection": "staten_island_ferry",
  "externalLand": "nyc_counties"
}
```

Most locations should not need a hook.

## Manifest Shape

Each `locations/<slug>.json` must include:

- `slug`
- `displayName`
- `shortName`, optional and defaults to `displayName`
- `areaKind`
- `outputPath`
- `cityOutputPath`
- `transit`
- `coverage`
- `context`
- `ui`

`transit` contains:

- `gtfsPath`
- `gtfsUrl`, optional
- `gtfsMember`, optional
- `stationSource`
- `includeRouteTypes`
- `includeRouteIds`
- `excludeRouteIds`
- `servicePolicy`, optional

`coverage` contains:

- `areasPath`
- `areasUrl`, optional
- `areaNameProperty`
- `areaIncludeNames`, optional
- `where`, optional
- `landAreasPath`, optional
- `landAreasUrl`, optional
- `landWhere`, optional
- `landIncludeNames`, optional

`context` contains:

- `parksPath`, optional
- `parkAreaProperty`, optional
- `parkAreaMin`
- `streetsPath`, optional
- `externalLand`, optional
- `countiesKmlPath`, optional

`ui` contains:

- `searchQuerySuffix`
- `searchViewbox`
- `shareText`
- `dataCredits`
- `downloadPrefix`
- `urlLabel`
- `emojiBurst`, optional. If omitted, `site/app.js` uses a generic city/transit emoji fallback.

## Frontend Registry

Generate `site/data/locations.json` from the manifests. This file becomes the frontend registry:

```json
{
  "defaultSlug": "nyc",
  "cities": [
    {
      "slug": "nyc",
      "displayName": "New York City",
      "shortName": "NYC",
      "dataUrl": "./data/nyc/commute_map_data.json",
      "urlLabel": "castrio.me/nyc",
      "emojiBurst": ["🗽", "🌆", "🏙️", "🚕", "🍎"]
    }
  ]
}
```

`site/app.js` should stop hardcoding supported city slugs and city-specific emoji sets. It should load `locations.json`, detect the requested city from query/path, validate it against the registry, then fetch that city's data URL.

Generic emoji themes such as `github`, `transit`, `maps`, `parks`, and `coffee` can remain in `app.js`. City-specific emoji should come from `locations.json` only when a manifest provides `ui.emojiBurst`; otherwise `app.js` should use a generic city/transit fallback.

## Location Documentation

Add `locations/README.md` to document the manifest schema. It should be prescriptive enough for future agents and include:

- required and optional fields;
- the default behavior for optional `shortName`;
- the difference between labeled `coverage.areasPath` and broader `coverage.landAreasPath`;
- the fixed-stop urban transit policy;
- why route allowlists must be explicit after route inspection;
- when `transit.gtfsMember` is needed;
- when a Python hook is acceptable;
- source attribution expectations.

Add `docs/ADDING_LOCATION.md` as the procedural guide for adding cities. It should tell agents to:

1. find official/public static GTFS;
2. add a draft manifest;
3. build once with broad filters only when necessary;
4. inspect route IDs;
5. replace broad filters with explicit `includeRouteIds`;
6. choose labeled areas separately from broader land coverage;
7. add smoke checks for route IDs, excluded modes, central station, and unlabeled land;
8. update Worker/Wrangler route configuration when the city should be deployable;
9. run `npm run check`;
10. commit one city at a time.

The docs should explicitly warn: do not include commuter rail, do not include ordinary mixed-traffic buses, do not treat unlabeled municipalities as water, and stop if a GTFS source is gated behind authentication.

## Worker And Wrangler Consistency

`src/worker.js` can keep its static `PATH_PREFIXES` array for now, but add a checker that ensures it matches manifest slugs. `wrangler.jsonc` also remains static because Cloudflare route config is deployment configuration, but the checker should verify that every manifest slug has a corresponding route pattern.

This keeps local behavior simple and prevents drift.

## Validation

Add `scripts/check_location_manifests.py` to validate:

- every `locations/*.json` is valid JSON;
- filename stem matches `slug`;
- slugs are unique;
- required top-level and nested fields exist;
- relative paths do not escape the repository;
- route include/exclude fields are arrays of strings;
- non-NYC manifests define `coverage.landAreasPath` unless explicitly documented later;
- `site/app.js` no longer hardcodes per-city supported slug lists;
- `src/worker.js` prefixes match manifest slugs;
- `wrangler.jsonc` routes include each manifest slug.
- validation failures for non-obvious rules should point to `locations/README.md` or `docs/ADDING_LOCATION.md`.

Add the manifest check to `npm run check`.

## Migration Requirements

The migration must not change generated commute data for existing locations except for the new generated `site/data/locations.json` registry.

For each current location:

- convert the existing Python manifest entry to `locations/<slug>.json`;
- keep route allowlists and source URLs identical;
- preserve NYC's special behavior through named hooks;
- preserve nested GTFS behavior through `transit.gtfsMember`;
- preserve `landMask` behavior for Boston, Chicago, Philadelphia, and Montreal.

## Risks

- JSON cannot represent Python `Path` or `set` objects, so the loader must normalize strings to `Path` and arrays to `set` where the builder expects sets.
- JSON cannot include comments, so field names and validation errors need to be clear.
- `site/app.js` currently computes `DATA_URL` before fetching any registry. Initialization must become registry-first.
- Wrangler routes are deployment config and cannot be fully generated at runtime; a checker is the right first step.
