#!/usr/bin/env python3
"""Validate location manifests and routing registry consistency."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_DIR = ROOT / "locations"
WORKER_PATH = ROOT / "src" / "worker.js"
WRANGLER_PATH = ROOT / "wrangler.jsonc"
FRONTEND_REGISTRY_PATH = ROOT / "site" / "data" / "locations.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "slug",
    "displayName",
    "areaKind",
    "outputPath",
    "cityOutputPath",
    "transit",
    "coverage",
    "context",
    "ui",
}
TRANSIT_ROUTE_LIST_KEYS = ("includeRouteTypes", "includeRouteIds", "excludeRouteIds")
PATH_KEYS = (
    "outputPath",
    "cityOutputPath",
    "transit.gtfsPath",
    "coverage.areasPath",
    "coverage.landAreasPath",
    "context.parksPath",
    "context.streetsPath",
    "context.countiesKmlPath",
)


def fail(message: str) -> None:
    print(f"check_location_manifests.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {error}")


def nested_value(manifest: dict, dotted_key: str):
    value = manifest
    for key in dotted_key.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def require_string_list(value, label: str) -> None:
    require(isinstance(value, list), f"{label} must be a list. See locations/README.md.")
    require(all(isinstance(item, str) for item in value), f"{label} must contain only strings. See locations/README.md.")


def require_repo_relative_path(value, label: str) -> None:
    if value is None:
        return
    require(isinstance(value, str), f"{label} must be a repository-relative path string. See locations/README.md.")
    path = Path(value)
    require(not path.is_absolute(), f"{label} must be relative, not absolute. See locations/README.md.")
    resolved = (ROOT / path).resolve()
    root_resolved = ROOT.resolve()
    require(
        resolved == root_resolved or root_resolved in resolved.parents,
        f"{label} escapes the repository. See locations/README.md.",
    )


def strip_json_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def load_manifests() -> dict[str, dict]:
    manifests = {}
    for path in sorted(LOCATIONS_DIR.glob("*.json")):
        manifest = load_json(path)
        slug = manifest.get("slug")
        require(slug == path.stem, f"{path.relative_to(ROOT)} slug must match filename stem.")
        missing = sorted(REQUIRED_TOP_LEVEL_KEYS - manifest.keys())
        require(not missing, f"{path.relative_to(ROOT)} missing required keys: {', '.join(missing)}")
        require(isinstance(slug, str) and slug, f"{path.relative_to(ROOT)} slug must be a non-empty string.")
        require(isinstance(manifest["displayName"], str) and manifest["displayName"], f"{slug} displayName is required.")
        if "shortName" in manifest:
            require(isinstance(manifest["shortName"], str) and manifest["shortName"], f"{slug} shortName must be a non-empty string if present.")

        transit = manifest["transit"]
        require(isinstance(transit, dict), f"{slug} transit must be an object. See locations/README.md.")
        for key in TRANSIT_ROUTE_LIST_KEYS:
            require_string_list(transit.get(key, []), f"{slug} transit.{key}")

        coverage = manifest["coverage"]
        require(isinstance(coverage, dict), f"{slug} coverage must be an object. See locations/README.md.")
        require(
            slug == "nyc" or coverage.get("landAreasPath"),
            f"{slug} coverage.landAreasPath is required for non-NYC locations. Do not treat unlabeled municipalities as water; see docs/ADDING_LOCATION.md.",
        )
        for key in ("areaIncludeNames", "landIncludeNames"):
            if key in coverage:
                require_string_list(coverage[key], f"{slug} coverage.{key}")

        ui = manifest["ui"]
        require(isinstance(ui, dict), f"{slug} ui must be an object. See locations/README.md.")
        if "emojiBurst" in ui:
            require_string_list(ui["emojiBurst"], f"{slug} ui.emojiBurst")

        for key in PATH_KEYS:
            require_repo_relative_path(nested_value(manifest, key), f"{slug} {key}")

        manifests[slug] = manifest

    require(manifests, f"No manifests found in {LOCATIONS_DIR.relative_to(ROOT)}.")
    return manifests


def check_worker_routes(slugs: set[str]) -> None:
    worker_source = WORKER_PATH.read_text(encoding="utf-8")
    for slug in sorted(slugs):
        require(f'"/{slug}"' in worker_source, f"src/worker.js missing /{slug} path prefix.")


def check_wrangler_routes(slugs: set[str]) -> None:
    config = json.loads(strip_json_comments(WRANGLER_PATH.read_text(encoding="utf-8")))
    patterns = {route.get("pattern") for route in config.get("routes", [])}
    for slug in sorted(slugs):
        require(f"castrio.me/{slug}*" in patterns, f"wrangler.jsonc missing castrio.me/{slug}* route.")


def check_frontend_registry(slugs: set[str]) -> None:
    if not FRONTEND_REGISTRY_PATH.exists():
        return
    registry = load_json(FRONTEND_REGISTRY_PATH)
    registry_slugs = {city.get("slug") for city in registry.get("cities", [])}
    require(registry_slugs == slugs, "site/data/locations.json slugs do not match locations/*.json; rebuild with build_commute_site_data.py.")
    require(registry.get("defaultSlug") in slugs, "site/data/locations.json defaultSlug is not a manifest slug.")


def main() -> None:
    manifests = load_manifests()
    slugs = set(manifests)
    check_worker_routes(slugs)
    check_wrangler_routes(slugs)
    check_frontend_registry(slugs)
    print(f"location manifests: ok ({', '.join(sorted(slugs))})")


if __name__ == "__main__":
    main()
