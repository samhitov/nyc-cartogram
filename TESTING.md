# Testing

This repo uses lightweight checks instead of a browser test framework.

## Automated Checks

Run:

```bash
npm run check
```

This verifies:

- generated NYC and Boston commute data exist and have the expected structure
- NYC still includes the Staten Island Ferry route
- Boston includes only the rapid-transit routes and excludes Silver Line IDs
- the main browser JavaScript parses with Node

## Manual Browser Smoke Tests

Run the static preview:

```bash
python3 -m http.server 8000
```

Then check:

- `http://localhost:8000/site/?city=nyc`
- `http://localhost:8000/site/?city=boston`

Verify for each city:

- the map loads without a data error
- the page title and copy match the city
- search returns city-appropriate results
- hover/click pins an origin
- warp, heatmap, and outline toggles work
- share/download text uses the right city name and URL label

For deep links, also check:

- `http://localhost:8000/site/?city=nyc&origin=40.71267,-73.92366`
- `http://localhost:8000/site/?city=boston&origin=42.36008,-71.05888`

If you run Wrangler locally:

```bash
pnpm run dev
```

Also check:

- `/nyc/`
- `/boston/`
- `/nyc/@40.71267,-73.92366`
- `/boston/@42.36008,-71.05888`

