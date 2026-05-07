#!/usr/bin/env python3
"""Validate generated commute map data without pinning volatile source counts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "nyc": ROOT / "site" / "data" / "nyc" / "commute_map_data.json",
    "boston": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
    "chicago": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
}
BOSTON_RAPID_ROUTES = {"Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E", "Mattapan"}
SILVER_LINE_ROUTE_IDS = {"741", "742", "743", "746", "749", "751"}
CHICAGO_L_ROUTES = {"Red", "Blue", "Brn", "G", "Org", "Pink", "P", "Y"}


def fail(message: str) -> None:
    print(f"check_commute_data.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_dataset(city: str, path: Path) -> dict:
    require(path.exists(), f"{city} data is missing at {path.relative_to(ROOT)}; run build_commute_site_data.py")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{city} data is not valid JSON: {error}")


def check_common(city: str, data: dict) -> None:
    meta = data.get("meta")
    require(isinstance(meta, dict), f"{city} missing meta")
    require(meta.get("city") == city, f"{city} meta.city mismatch")
    require(isinstance(meta.get("bounds"), list) and len(meta["bounds"]) == 4, f"{city} missing bounds")
    require(isinstance(meta.get("gridCols"), int) and meta["gridCols"] > 0, f"{city} invalid gridCols")
    require(isinstance(meta.get("gridRows"), int) and meta["gridRows"] > 0, f"{city} invalid gridRows")
    require(meta.get("displayName"), f"{city} missing displayName")
    require(meta.get("searchQuerySuffix"), f"{city} missing searchQuerySuffix")
    require(meta.get("searchViewbox"), f"{city} missing searchViewbox")

    for key in ("areas", "boroughs", "parks", "streets", "routes", "stations", "routeStates", "stationStates", "adjacency", "cells", "mask", "routeStyles"):
        require(key in data, f"{city} missing {key}")

    for key in ("areas", "boroughs", "routes", "stations", "routeStates", "stationStates", "adjacency", "cells", "routeStyles"):
        require(len(data[key]) > 0, f"{city} {key} is empty")

    require(len(data["mask"]) == meta["gridCols"] * meta["gridRows"], f"{city} mask size does not match grid")
    require(len(data["routeStates"]) == len(data["adjacency"]), f"{city} routeStates/adjacency length mismatch")
    require(len(data["stations"]) == len(data["stationStates"]), f"{city} stations/stationStates length mismatch")

    station_count = len(data["stations"])
    route_state_count = len(data["routeStates"])
    route_style_ids = set(data["routeStyles"])

    for index, route_state in enumerate(data["routeStates"]):
        station_index = route_state.get("stationIndex")
        route_id = route_state.get("routeId")
        require(isinstance(station_index, int) and 0 <= station_index < station_count, f"{city} routeState {index} invalid stationIndex")
        require(route_id in route_style_ids, f"{city} routeState {index} unknown routeId {route_id}")

    listed_state_indexes = set()
    for station_index, state_indexes in enumerate(data["stationStates"]):
        require(isinstance(state_indexes, list), f"{city} stationStates[{station_index}] is not a list")
        for state_index in state_indexes:
            require(isinstance(state_index, int) and 0 <= state_index < route_state_count, f"{city} stationStates[{station_index}] invalid route state")
            listed_state_indexes.add(state_index)
            require(
                data["routeStates"][state_index]["stationIndex"] == station_index,
                f"{city} stationStates[{station_index}] references route state for another station",
            )
    require(listed_state_indexes == set(range(route_state_count)), f"{city} stationStates does not list every route state")

    for from_state, edges in enumerate(data["adjacency"]):
        require(isinstance(edges, list), f"{city} adjacency[{from_state}] is not a list")
        for edge in edges:
            require(isinstance(edge, list) and len(edge) == 2, f"{city} adjacency[{from_state}] invalid edge")
            to_state, weight = edge
            require(isinstance(to_state, int) and 0 <= to_state < route_state_count, f"{city} adjacency[{from_state}] invalid destination")
            require(isinstance(weight, (int, float)) and weight > 0, f"{city} adjacency[{from_state}] invalid weight")

    for station in data["stations"]:
        require(station.get("id"), f"{city} station missing id")
        require(station.get("name"), f"{city} station missing name")
        require(isinstance(station.get("point"), list) and len(station["point"]) == 2, f"{city} station has invalid point")
        require(isinstance(station.get("routes"), list), f"{city} station has invalid routes")
        for route_id in station["routes"]:
            require(route_id in route_style_ids, f"{city} station {station.get('name')} has unknown route {route_id}")


def check_nyc(data: dict) -> None:
    require("SIF" in data["routeStyles"], "nyc missing Staten Island Ferry route")
    require(any(area.get("name") == "Manhattan" for area in data["areas"]), "nyc missing Manhattan area")


def check_boston(data: dict) -> None:
    route_ids = set(data["routeStyles"])
    require(BOSTON_RAPID_ROUTES.issubset(route_ids), "boston missing one or more rapid-transit routes")
    require(route_ids.isdisjoint(SILVER_LINE_ROUTE_IDS), "boston unexpectedly includes Silver Line route ids")
    require(any(area.get("name") == "Boston" for area in data["areas"]), "boston missing Boston municipality")
    require(any(station.get("name") == "Park Street" for station in data["stations"]), "boston missing Park Street station")


def check_chicago(data: dict) -> None:
    route_ids = set(data["routeStyles"])
    require(CHICAGO_L_ROUTES.issubset(route_ids), "chicago missing one or more CTA L routes")
    require(all(route_id in CHICAGO_L_ROUTES for route_id in route_ids), "chicago includes non-L route ids")
    station_names = {station.get("name") for station in data["stations"]}
    require("Clark/Lake" in station_names or "State/Lake" in station_names, "chicago missing expected Loop station")


def main() -> None:
    for city, path in DATASETS.items():
        if city == "chicago" and not path.exists():
            print("chicago: skipped; data not generated yet")
            continue
        data = load_dataset(city, path)
        check_common(city, data)
        if city == "nyc":
            check_nyc(data)
        elif city == "boston":
            check_boston(data)
        elif city == "chicago":
            check_chicago(data)
        print(f"{city}: ok")


if __name__ == "__main__":
    main()
