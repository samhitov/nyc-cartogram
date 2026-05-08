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
`ui.searchCountryCodes` is optional. If present, it is passed to Nominatim as a lowercase comma-separated `countrycodes` filter.
`ui.sourceLinks` is optional but recommended for each supported location. Use it for transit, boundary, and context data sources that should replace the default footer links.
