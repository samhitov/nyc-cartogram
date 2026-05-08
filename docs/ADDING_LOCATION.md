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

## Area Labeling Notes

Think about three separate geographic concepts when choosing labels:

- Primary transit service areas: the main labeled/display polygons in `coverage.areaIncludeNames`.
- Land-mask areas: broader nearby land polygons used so unlabeled municipalities are not treated as water.
- Context labels: optional future labels that help orient the map without implying the area is a primary served area.

NYC works well with prominent borough labels because the five boroughs are both administrative areas and strong mental-map anchors.
Other metros may need a different treatment. For example, Montreal can look sparse if only Montréal, Laval, and Longueuil are labeled, even though the land mask includes nearby municipalities such as Westmount, Dorval, Brossard, or Saint-Lambert.

Do not automatically label every land-mask municipality.
If this becomes a problem, add a manifest-driven context-label feature later: render selected surrounding municipalities smaller and lighter than primary labels, avoid strong borders for them, and keep the distinction clear between transit service areas and geographic context.
