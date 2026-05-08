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
