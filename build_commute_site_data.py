#!/usr/bin/env python3
"""Build compact data assets for the interactive commute-time website."""

from __future__ import annotations

import csv
import json
import math
import argparse
import statistics
import urllib.parse
import urllib.request
import urllib.error
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SITE_DATA_PATH = ROOT / "site" / "data" / "commute_map_data.json"

NYC_BOROUGHS_PATH = DATA_DIR / "borough_boundaries.geojson"
NYC_PARKS_PATH = DATA_DIR / "parks_open_space.geojson"
NYC_STREETS_PATH = DATA_DIR / "osm_major_streets.json"
NYC_GTFS_PATH = DATA_DIR / "mta_gtfs_subway.zip"
NYC_COUNTIES_KML_ZIP_PATH = DATA_DIR / "cb_2024_us_county_500k.zip"
BOSTON_AREAS_PATH = DATA_DIR / "boston_municipalities.geojson"
BOSTON_LAND_AREAS_PATH = DATA_DIR / "boston_land_municipalities.geojson"
BOSTON_OPEN_SPACE_PATH = DATA_DIR / "boston_open_space.geojson"
BOSTON_STREETS_PATH = DATA_DIR / "boston_osm_major_streets.json"
BOSTON_GTFS_PATH = DATA_DIR / "mbta_gtfs.zip"
CHICAGO_DATA_DIR = DATA_DIR / "chicago"
CHICAGO_AREAS_PATH = CHICAGO_DATA_DIR / "municipalities.geojson"
CHICAGO_LAND_AREAS_PATH = CHICAGO_DATA_DIR / "land_municipalities.geojson"
CHICAGO_STREETS_PATH = CHICAGO_DATA_DIR / "osm_major_streets.json"
CHICAGO_GTFS_PATH = CHICAGO_DATA_DIR / "cta_gtfs.zip"

BOSTON_MUNICIPALITIES = (
    "Boston",
    "Brookline",
    "Newton",
    "Cambridge",
    "Somerville",
    "Quincy",
    "Milton",
    "Revere",
    "Medford",
    "Malden",
    "Braintree",
)
BOSTON_RAPID_TRANSIT_ROUTES = {
    "Red",
    "Orange",
    "Blue",
    "Green-B",
    "Green-C",
    "Green-D",
    "Green-E",
    "Mattapan",
}
BOSTON_MBTA_GTFS_URL = "https://cdn.mbta.com/MBTA_GTFS.zip"
BOSTON_MUNICIPALITIES_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/DPH/Political_Boundaries/MapServer/1/query"
)
BOSTON_OPEN_SPACE_URL = (
    "https://gis.eea.mass.gov/server/rest/services/Protected_and_Recreational_OpenSpace_Polygons/FeatureServer/0/query"
)
BOSTON_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CHICAGO_CTA_GTFS_URL = "https://www.transitchicago.com/downloads/sch_data/google_transit.zip"
CHICAGO_MUNICIPALITIES_URL = (
    "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/"
    "Cook_County_Municipalities/FeatureServer/0/query"
)
CHICAGO_MUNICIPALITIES = (
    "Chicago",
    "Cicero",
    "Evanston",
    "Forest Park",
    "Oak Park",
    "Rosemont",
    "Skokie",
    "Wilmette",
)

GRID_COLS = 160
GRID_ROWS = 160
MIN_PARK_AREA = 70_000.0
# Keep walking assumptions close to a normal NYC walking pace so first/last-mile
# time does not dominate otherwise reasonable subway trips.
WALK_METERS_PER_MINUTE = 80.0
ACCESS_WALK_METERS_PER_MINUTE = 75.0
STATION_ACCESS_PENALTY = 3.5
CELL_NEAREST_STATIONS = 4
ORIGIN_NEAREST_STATIONS = 5
MAX_SHAPES_PER_ROUTE_DIRECTION = 2
INTER_COMPLEX_WALK_RADIUS = 260.0
INTER_COMPLEX_WALK_PENALTY = 2.0
DEFAULT_BOARD_WAIT = 4.0
TRANSFER_PENALTY = 4.0
INTER_COMPLEX_TRANSFER_PENALTY = 7.0
STATEN_ISLAND_FERRY_ROUTE_ID = "SIF"
STATEN_ISLAND_FERRY_WAIT = 7.5
STATEN_ISLAND_FERRY_TRAVEL_MINUTES = 25.0
STATEN_ISLAND_FERRY_TERMINALS = ("501", "635")

Point = Tuple[float, float]
Ring = List[Point]
Polygon = List[Ring]
MultiPolygon = List[Polygon]


LOCATION_CONFIGS = {
    "nyc": {
        "slug": "nyc",
        "display_name": "New York City",
        "short_name": "NYC",
        "area_kind": "boroughs",
        "output_path": SITE_DATA_PATH,
        "city_output_path": ROOT / "site" / "data" / "nyc" / "commute_map_data.json",
        "transit": {
            "gtfs_path": NYC_GTFS_PATH,
            "station_source": "nyc_station_json",
            "include_route_types": {"1"},
            "include_route_ids": {"SI"},
            "exclude_route_ids": set(),
        },
        "coverage": {
            "areas_path": NYC_BOROUGHS_PATH,
            "area_name_property": "boroname",
            "land_areas_path": None,
        },
        "context": {
            "parks_path": NYC_PARKS_PATH,
            "park_area_property": "shape_area",
            "park_area_min": 70_000.0,
            "streets_path": NYC_STREETS_PATH,
            "external_land": "nyc_counties",
            "counties_kml_path": NYC_COUNTIES_KML_ZIP_PATH,
        },
        "hooks": {
            "manual_connection": "staten_island_ferry",
        },
        "ui": {
            "search_query_suffix": "New York City",
            "search_viewbox": "-74.30,40.95,-73.65,40.45",
            "share_text": "Explore New York City by subway commute time with this interactive transit cartogram.",
            "data_credits": "MTA GTFS, NYC Open Data, OpenStreetMap",
            "download_prefix": "nyc-commute-cartogram",
            "url_label": "castrio.me/nyc",
        },
    },
    "boston": {
        "slug": "boston",
        "display_name": "Boston",
        "short_name": "Boston",
        "area_kind": "municipalities",
        "output_path": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
        "city_output_path": ROOT / "site" / "data" / "boston" / "commute_map_data.json",
        "transit": {
            "gtfs_path": BOSTON_GTFS_PATH,
            "gtfs_url": BOSTON_MBTA_GTFS_URL,
            "station_source": "gtfs_parent_stations",
            "include_route_types": set(),
            "include_route_ids": BOSTON_RAPID_TRANSIT_ROUTES,
            "exclude_route_ids": set(),
        },
        "coverage": {
            "areas_path": BOSTON_AREAS_PATH,
            "areas_url": BOSTON_MUNICIPALITIES_URL,
            "area_name_property": "TOWNNAME",
            "area_include_names": set(BOSTON_MUNICIPALITIES),
            "land_areas_path": BOSTON_LAND_AREAS_PATH,
            "land_areas_url": BOSTON_MUNICIPALITIES_URL,
        },
        "context": {
            "parks_path": BOSTON_OPEN_SPACE_PATH,
            "park_area_property": "GIS_ACRES",
            "park_area_min": 1.6,
            "streets_path": BOSTON_STREETS_PATH,
            "external_land": None,
        },
        "hooks": {
            "manual_connection": None,
        },
        "ui": {
            "search_query_suffix": "Massachusetts",
            "search_viewbox": "-71.30,42.45,-70.85,42.15",
            "share_text": "Explore Boston by MBTA rapid-transit commute time with this interactive transit cartogram.",
            "data_credits": "MBTA/MassDOT GTFS, MassGIS, OpenStreetMap",
            "download_prefix": "boston-commute-cartogram",
            "url_label": "castrio.me/boston",
        },
    },
    "chicago": {
        "slug": "chicago",
        "display_name": "Chicago",
        "short_name": "Chicago",
        "area_kind": "municipalities",
        "output_path": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
        "city_output_path": ROOT / "site" / "data" / "chicago" / "commute_map_data.json",
        "transit": {
            "gtfs_path": CHICAGO_GTFS_PATH,
            "gtfs_url": CHICAGO_CTA_GTFS_URL,
            "station_source": "gtfs_parent_stations",
            "include_route_types": {"1"},
            "include_route_ids": set(),
            "exclude_route_ids": set(),
            "service_policy": "CTA L only. Excludes CTA buses and Metra.",
        },
        "coverage": {
            "areas_path": CHICAGO_AREAS_PATH,
            "areas_url": CHICAGO_MUNICIPALITIES_URL,
            "area_name_property": "NAME",
            "area_include_names": set(CHICAGO_MUNICIPALITIES),
            "land_areas_path": CHICAGO_LAND_AREAS_PATH,
            "land_areas_url": CHICAGO_MUNICIPALITIES_URL,
        },
        "context": {
            "parks_path": None,
            "park_area_property": None,
            "park_area_min": 70000.0,
            "streets_path": CHICAGO_STREETS_PATH,
        },
        "hooks": {
            "manual_connection": None,
        },
        "ui": {
            "search_query_suffix": "Chicago, Illinois",
            "search_viewbox": "-87.95,42.10,-87.45,41.55",
            "share_text": "Explore Chicago by CTA L commute time with this interactive transit cartogram.",
            "data_credits": "CTA GTFS, Cook County open data, OpenStreetMap",
            "download_prefix": "chicago-commute-cartogram",
            "url_label": "castrio.me/chicago",
        },
    },
}


def transit_config(config: dict) -> dict:
    return config["transit"]


def coverage_config(config: dict) -> dict:
    return config["coverage"]


def context_config(config: dict) -> dict:
    return config["context"]


def hooks_config(config: dict) -> dict:
    return config.get("hooks", {})


def ui_config(config: dict) -> dict:
    return config["ui"]


def round_point(point: Point) -> List[float]:
    return [round(point[0], 1), round(point[1], 1)]


def round_path(points: Sequence[Point]) -> List[List[float]]:
    return [round_point(point) for point in points]


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def download_file(url: str, path: Path, user_agent: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url)
    if user_agent:
        request.add_header("User-Agent", user_agent)
    with urllib.request.urlopen(request) as response:
        path.write_bytes(response.read())


def fetch_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{query}") as response:
        return json.loads(response.read().decode("utf-8"))


def query_arcgis_geojson(url: str, params: dict, page_size: int = 2000) -> dict:
    features = []
    offset = 0
    while True:
        payload = fetch_json(
            url,
            {
                **params,
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": page_size,
            },
        )
        batch = payload.get("features", [])
        features.extend(batch)
        if len(batch) < page_size and not payload.get("properties", {}).get("exceededTransferLimit"):
            break
        offset += page_size
    return {"type": "FeatureCollection", "features": features}


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def geojson_has_features(path: Path) -> bool:
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("features"))


def ensure_static_gtfs(config: dict) -> None:
    transit = transit_config(config)
    gtfs_path = transit["gtfs_path"]
    gtfs_url = transit.get("gtfs_url")
    if gtfs_path.exists():
        return
    if not gtfs_url:
        raise FileNotFoundError(f"Missing GTFS file for {config['slug']}: {gtfs_path}")
    download_file(gtfs_url, gtfs_path, user_agent=f"nyc-cartogram-{config['slug']}-data-builder/1.0")


def ensure_arcgis_coverage(config: dict) -> None:
    coverage = coverage_config(config)
    areas_path = coverage["areas_path"]
    if areas_path.exists() and geojson_has_features(areas_path):
        return
    areas_url = coverage.get("areas_url")
    if not areas_url:
        raise FileNotFoundError(f"Missing area file for {config['slug']}: {areas_path}")

    include_names = coverage.get("area_include_names")
    name_property = coverage["area_name_property"]
    where = "1=1"
    if include_names:
        quoted = "', '".join(sorted(include_names))
        where = f"{name_property} IN ('{quoted}')"

    payload = query_arcgis_geojson(
        areas_url,
        {
            "where": where,
            "outFields": "*",
            "outSR": 4326,
            "returnGeometry": "true",
        },
    )
    write_json(areas_path, payload)


def ensure_arcgis_land_coverage(config: dict) -> None:
    coverage = coverage_config(config)
    land_areas_path = coverage.get("land_areas_path")
    if not land_areas_path:
        return
    if land_areas_path.exists() and geojson_has_features(land_areas_path):
        return
    land_areas_url = coverage.get("land_areas_url")
    if not land_areas_url:
        raise FileNotFoundError(f"Missing land area file for {config['slug']}: {land_areas_path}")

    payload = query_arcgis_geojson(
        land_areas_url,
        {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "returnGeometry": "true",
        },
    )
    write_json(land_areas_path, payload)


def ensure_source_data(config: dict) -> None:
    ensure_static_gtfs(config)
    ensure_arcgis_coverage(config)
    ensure_arcgis_land_coverage(config)


def ensure_overpass_major_streets(config: dict, bbox_lonlat: Tuple[float, float, float, float]) -> None:
    streets_path = context_config(config).get("streets_path")
    if not streets_path or streets_path.exists():
        return

    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    overpass_query = f"""
    [out:json][timeout:60];
    (
      way["highway"~"^(motorway|trunk|primary)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out tags geom;
    """
    query = urllib.parse.urlencode({"data": overpass_query}).encode("utf-8")
    request = urllib.request.Request(
        BOSTON_OVERPASS_URL,
        data=query,
        headers={"User-Agent": f"nyc-cartogram-{config['slug']}-data-builder/1.0"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            streets_path.parent.mkdir(parents=True, exist_ok=True)
            streets_path.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        print(f"Warning: could not fetch {config['display_name']} OSM streets ({error}); continuing without streets.")


def ensure_context_data(config: dict, bbox_lonlat: Tuple[float, float, float, float]) -> None:
    context = context_config(config)
    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    if config["slug"] == "boston" and not context["parks_path"].exists():
        payload = query_arcgis_geojson(
            BOSTON_OPEN_SPACE_URL,
            {
                "where": "1=1",
                "outFields": "SITE_NAME,GIS_ACRES,PRIM_PURP",
                "outSR": 4326,
                "returnGeometry": "true",
                "geometry": json.dumps(
                    {
                        "xmin": min_lon,
                        "ymin": min_lat,
                        "xmax": max_lon,
                        "ymax": max_lat,
                        "spatialReference": {"wkid": 4326},
                    }
                ),
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
            },
            page_size=4000,
        )
        write_json(context["parks_path"], payload)

    ensure_overpass_major_streets(config, bbox_lonlat)


def lonlat_to_xy(lon: float, lat: float, lat0: float) -> Point:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(lat0))
    return lon * meters_per_deg_lon, lat * meters_per_deg_lat


def xy_to_lonlat(point: Point, lat0: float) -> Point:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(lat0))
    return point[0] / meters_per_deg_lon, point[1] / meters_per_deg_lat


def iter_polygon_coordinate_sets(geometry: dict) -> Iterable[list]:
    if not geometry:
        return
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]


def average_area_latitude(payload: dict) -> float:
    total = 0.0
    count = 0
    for feature in payload["features"]:
        for polygon in iter_polygon_coordinate_sets(feature.get("geometry")):
            for ring in polygon:
                for _, lat in ring:
                    total += lat
                    count += 1
    return total / max(count, 1)


def ring_area(ring: Sequence[Point]) -> float:
    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def polygon_centroid(ring: Sequence[Point]) -> Point:
    area = ring_area(ring) or 1.0
    factor = 1.0 / (6.0 * area)
    cx = 0.0
    cy = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return cx * factor, cy * factor


def simplify_polyline(points: Sequence[Point], min_distance: float) -> List[Point]:
    if len(points) <= 2:
        return list(points)
    simplified = [points[0]]
    for point in points[1:-1]:
        if math.hypot(point[0] - simplified[-1][0], point[1] - simplified[-1][1]) >= min_distance:
            simplified.append(point)
    if points[-1] != simplified[-1]:
        simplified.append(points[-1])
    return simplified


def simplify_ring(ring: Sequence[Point], min_distance: float) -> Ring:
    if len(ring) <= 4:
        return list(ring)
    core = list(ring[:-1]) if ring[0] == ring[-1] else list(ring)
    simplified = [core[0]]
    for point in core[1:]:
        if math.hypot(point[0] - simplified[-1][0], point[1] - simplified[-1][1]) >= min_distance:
            simplified.append(point)
    if len(simplified) < 3:
        simplified = core[:3]
    simplified.append(simplified[0])
    return simplified


def bounds_of_ring(ring: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [x for x, _ in ring]
    ys = [y for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def bounds_of_multipolygon(multipolygon: MultiPolygon) -> Tuple[float, float, float, float]:
    xs = [x for polygon in multipolygon for ring in polygon for x, _ in ring]
    ys = [y for polygon in multipolygon for ring in polygon for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def bounds_of_points(points: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def polygon_bounds(polygon: Polygon) -> Tuple[float, float, float, float]:
    xs = [point[0] for ring in polygon for point in ring]
    ys = [point[1] for ring in polygon for point in ring]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_ring(point: Point, ring: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersects = (yi > y) != (yj > y)
        if intersects:
            x_hit = (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
            if x < x_hit:
                inside = not inside
        j = i
    return inside


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    if not polygon:
        return False
    if not point_in_ring(point, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def point_in_multipolygon(point: Point, multipolygon: MultiPolygon) -> bool:
    return any(point_in_polygon(point, polygon) for polygon in multipolygon)


def extract_areas(payload: dict, lat0: float, config: dict) -> Tuple[list, MultiPolygon]:
    areas = []
    all_polygons: MultiPolygon = []
    coverage = coverage_config(config)
    include_names = coverage.get("area_include_names")
    name_property = coverage["area_name_property"]
    for feature in payload["features"]:
        name = feature.get("properties", {}).get(name_property)
        if include_names and name not in include_names:
            continue
        multipolygon: MultiPolygon = []
        for polygon_coords in iter_polygon_coordinate_sets(feature.get("geometry")):
            polygon: Polygon = []
            for ring_coords in polygon_coords:
                ring = [lonlat_to_xy(lon, lat, lat0) for lon, lat in ring_coords]
                polygon.append(simplify_ring(ring, 120.0))
            multipolygon.append(polygon)
            all_polygons.append(polygon)
        if not multipolygon:
            continue
        largest_polygon = max(multipolygon, key=lambda polygon: abs(ring_area(polygon[0])))
        areas.append(
            {
                "name": name,
                "label": round_point(polygon_centroid(largest_polygon[0])),
                "polygons": [[round_path(ring) for ring in polygon] for polygon in multipolygon],
            }
        )
    return areas, all_polygons


def extract_land_mask(payload: dict, lat0: float, bbox: Tuple[float, float, float, float]) -> MultiPolygon:
    land_polygons: MultiPolygon = []
    for feature in payload["features"]:
        for polygon_coords in iter_polygon_coordinate_sets(feature.get("geometry")):
            polygon: Polygon = []
            for ring_coords in polygon_coords:
                ring = [lonlat_to_xy(lon, lat, lat0) for lon, lat in ring_coords]
                polygon.append(simplify_ring(ring, 120.0))
            if polygon and bbox_intersects(polygon_bounds(polygon), bbox):
                land_polygons.append(polygon)
    return land_polygons


def extract_parks(lat0: float, bbox: Tuple[float, float, float, float], config: dict) -> list:
    context = context_config(config)
    parks_path = context.get("parks_path")
    if not parks_path or not parks_path.exists():
        return []
    payload = load_json(parks_path)
    parks = []
    for feature in payload["features"]:
        try:
            area = float(feature["properties"].get(context["park_area_property"]) or 0.0)
        except (TypeError, ValueError):
            area = 0.0
        if area < context["park_area_min"]:
            continue
        geometry = feature.get("geometry")
        if not geometry:
            continue
        for polygon_coords in iter_polygon_coordinate_sets(geometry):
            polygon: Polygon = []
            for ring_coords in polygon_coords:
                ring = [lonlat_to_xy(lon, lat, lat0) for lon, lat in ring_coords]
                polygon.append(simplify_ring(ring, 90.0))
            if polygon and bbox_intersects(bounds_of_ring(polygon[0]), bbox):
                parks.append([round_path(ring) for ring in polygon])
    return parks


def extract_streets(lat0: float, bbox: Tuple[float, float, float, float], config: dict) -> list:
    streets_path = context_config(config).get("streets_path")
    if not streets_path or not streets_path.exists():
        return []
    payload = load_json(streets_path)
    allowed = {"motorway", "trunk", "primary"}
    streets = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        tags = element.get("tags", {})
        kind = tags.get("highway")
        if kind not in allowed or "geometry" not in element or "name" not in tags:
            continue
        points = [lonlat_to_xy(node["lon"], node["lat"], lat0) for node in element["geometry"]]
        if len(points) < 2:
            continue
        length = sum(distance for distance in (
            math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
            for i in range(len(points) - 1)
        ))
        if kind == "primary" and length < 900.0:
            continue
        simplified = simplify_polyline(points, 220.0)
        if len(simplified) < 2 or not bbox_intersects(bounds_of_points(simplified), bbox):
            continue
        streets.append({"kind": kind, "name": tags["name"], "points": round_path(simplified)})
    return streets


def parse_kml_coordinates(text: str, lat0: float) -> Ring:
    ring: Ring = []
    for item in text.replace("\n", " ").split():
        parts = item.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        ring.append(lonlat_to_xy(lon, lat, lat0))
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def build_external_land_polygons(
    lat0: float,
    bbox: Tuple[float, float, float, float],
    area_polygons: MultiPolygon,
    config: dict,
) -> list:
    context = context_config(config)
    if context.get("external_land") != "nyc_counties":
        return []
    counties_path = context["counties_kml_path"]
    if not counties_path.exists():
        return []

    include_states = {"NY", "NJ", "CT"}
    exclude_geoids = {"36005", "36047", "36061", "36081", "36085"}
    namespace = {"kml": "http://www.opengis.net/kml/2.2"}
    polygons = []

    with zipfile.ZipFile(counties_path) as archive:
      with archive.open("cb_2024_us_county_500k.kml") as handle:
        for _, placemark in ET.iterparse(handle, events=("end",)):
            if not placemark.tag.endswith("Placemark"):
                continue
            data = {
                item.attrib.get("name"): (item.text or "")
                for item in placemark.findall(".//kml:SimpleData", namespace)
            }
            geoid = data.get("GEOID")
            stusps = data.get("STUSPS")
            if geoid in exclude_geoids or stusps not in include_states:
                placemark.clear()
                continue

            multipolygon: MultiPolygon = []
            for polygon_node in placemark.findall(".//kml:Polygon", namespace):
                rings = []
                for ring_node in polygon_node.findall("./kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", namespace):
                    ring = parse_kml_coordinates(ring_node.text or "", lat0)
                    if len(ring) >= 4:
                        rings.append(simplify_ring(ring, 120.0))
                for ring_node in polygon_node.findall("./kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", namespace):
                    ring = parse_kml_coordinates(ring_node.text or "", lat0)
                    if len(ring) >= 4:
                        rings.append(simplify_ring(ring, 120.0))
                if rings:
                    multipolygon.append(rings)

            visible_polygons = []
            for polygon in multipolygon:
                if not bbox_intersects(bounds_of_ring(polygon[0]), bbox):
                    continue
                if point_in_multipolygon(polygon_centroid(polygon[0]), area_polygons):
                    continue
                visible_polygons.append([round_path(ring) for ring in polygon])
            if visible_polygons:
                polygons.extend(visible_polygons)
            placemark.clear()

    return polygons


def read_csv_from_zip(gtfs_path: Path, member: str) -> Iterable[dict]:
    with zipfile.ZipFile(gtfs_path) as archive:
        with archive.open(member) as handle:
            reader = csv.DictReader(line.decode("utf-8-sig") for line in handle)
            yield from reader


def parse_gtfs_time(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def route_is_included(row: dict, config: dict) -> bool:
    transit = transit_config(config)
    route_id = row.get("route_id")
    if route_id in transit.get("exclude_route_ids", set()):
        return False
    if route_id in transit.get("include_route_ids", set()):
        return True
    if row.get("route_type") in transit.get("include_route_types", set()):
        return True
    return False


def build_nyc_station_data(lat0: float, config: dict) -> Tuple[list, Dict[str, int], Dict[str, str]]:
    complex_info: Dict[str, dict] = {}
    stop_to_complex: Dict[str, str] = {}

    for row in load_json(DATA_DIR / "subway_stations.json"):
        complex_id = row["complex_id"]
        stop_code = row["gtfs_stop_id"]
        stop_to_complex[stop_code] = complex_id
        stop_to_complex[f"{stop_code}N"] = complex_id
        stop_to_complex[f"{stop_code}S"] = complex_id
        info = complex_info.setdefault(
            complex_id,
            {
                "id": complex_id,
                "name": row["stop_name"],
                "point": lonlat_to_xy(float(row["gtfs_longitude"]), float(row["gtfs_latitude"]), lat0),
                "routes": set(),
            },
        )
        routes = (row.get("daytime_routes") or "").split()
        info["routes"].update(route for route in routes if route)

    stations = []
    station_index_by_id: Dict[str, int] = {}
    for complex_id, info in sorted(complex_info.items(), key=lambda item: int(item[0])):
        station_index_by_id[complex_id] = len(stations)
        stations.append(info)

    for row in read_csv_from_zip(transit_config(config)["gtfs_path"], "stops.txt"):
        stop_id = row["stop_id"]
        parent_station = row.get("parent_station") or ""
        if stop_id not in stop_to_complex and parent_station and parent_station in stop_to_complex:
            stop_to_complex[stop_id] = stop_to_complex[parent_station]

    return stations, station_index_by_id, stop_to_complex


def build_gtfs_parent_station_data(config: dict, trips_by_id: dict, lat0: float) -> Tuple[list, Dict[str, int], Dict[str, str]]:
    gtfs_path = transit_config(config)["gtfs_path"]
    stops_by_id = {row["stop_id"]: row for row in read_csv_from_zip(gtfs_path, "stops.txt")}
    used_stop_ids = set()
    route_ids_by_parent: Dict[str, set] = defaultdict(set)

    for row in read_csv_from_zip(gtfs_path, "stop_times.txt"):
        trip = trips_by_id.get(row["trip_id"])
        if not trip:
            continue
        stop_id = row["stop_id"]
        stop = stops_by_id.get(stop_id)
        if not stop:
            continue
        parent_id = stop.get("parent_station") or stop_id
        used_stop_ids.add(stop_id)
        route_ids_by_parent[parent_id].add(trip["route_id"])

    station_rows = []
    stop_to_complex: Dict[str, str] = {}
    for parent_id, route_ids in route_ids_by_parent.items():
        parent = stops_by_id.get(parent_id)
        if not parent:
            children = [stops_by_id[stop_id] for stop_id in used_stop_ids if stops_by_id.get(stop_id, {}).get("parent_station") == parent_id]
            parent = children[0] if children else None
        if not parent:
            continue
        stop_to_complex[parent_id] = parent_id
        for stop_id, stop in stops_by_id.items():
            if stop_id == parent_id or stop.get("parent_station") == parent_id:
                stop_to_complex[stop_id] = parent_id
        station_rows.append(
            {
                "id": parent_id,
                "name": parent["stop_name"],
                "point": lonlat_to_xy(float(parent["stop_lon"]), float(parent["stop_lat"]), lat0),
                "routes": set(route_ids),
                "municipality": parent.get("municipality", ""),
            }
        )

    stations = sorted(station_rows, key=lambda station: station["name"])
    station_index_by_id = {station["id"]: index for index, station in enumerate(stations)}
    return stations, station_index_by_id, stop_to_complex


def build_routes_and_shapes(lat0: float, bbox: Tuple[float, float, float, float], config: dict) -> Tuple[dict, list, dict]:
    route_styles = {}
    gtfs_path = transit_config(config)["gtfs_path"]
    for row in read_csv_from_zip(gtfs_path, "routes.txt"):
        if not route_is_included(row, config):
            continue
        route_styles[row["route_id"]] = {
            "color": f"#{row['route_color'] or '808183'}",
            "textColor": f"#{row['route_text_color'] or 'FFFFFF'}",
            "label": row["route_short_name"] or row["route_long_name"].replace(" Line", "") or row["route_id"],
        }

    trips_by_id = {}
    shape_counts: Dict[Tuple[str, str], Counter[str]] = {}
    for row in read_csv_from_zip(gtfs_path, "trips.txt"):
        route_id = row["route_id"]
        if route_id not in route_styles:
            continue
        trips_by_id[row["trip_id"]] = {
            "route_id": route_id,
            "direction_id": row.get("direction_id", "0"),
            "service_id": row.get("service_id", ""),
        }
        shape_counts.setdefault((route_id, row.get("direction_id", "0")), Counter())[row["shape_id"]] += 1

    selected_shape_ids = {}
    for (route_id, _direction), counter in shape_counts.items():
        for shape_id, _count in counter.most_common(MAX_SHAPES_PER_ROUTE_DIRECTION):
            selected_shape_ids[shape_id] = route_id

    points_by_shape = defaultdict(list)
    for row in read_csv_from_zip(gtfs_path, "shapes.txt"):
        shape_id = row["shape_id"]
        if shape_id not in selected_shape_ids:
            continue
        point = lonlat_to_xy(float(row["shape_pt_lon"]), float(row["shape_pt_lat"]), lat0)
        points_by_shape[shape_id].append((int(row["shape_pt_sequence"]), point))

    shapes = []
    for shape_id, route_id in selected_shape_ids.items():
        points = [point for _, point in sorted(points_by_shape.get(shape_id, []))]
        points = simplify_polyline(points, 90.0)
        if len(points) < 2 or not bbox_intersects(bounds_of_points(points), bbox):
            continue
        shapes.append(
            {
                "routeId": route_id,
                "color": route_styles[route_id]["color"],
                "textColor": route_styles[route_id]["textColor"],
                "label": route_styles[route_id]["label"],
                "points": round_path(points),
            }
        )
    return route_styles, shapes, trips_by_id


def build_route_waits(trips_by_id: dict, config: dict) -> Dict[str, float]:
    departures_by_route_service: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    current_trip_id = None
    first_departure = None

    for row in read_csv_from_zip(transit_config(config)["gtfs_path"], "stop_times.txt"):
        trip_id = row["trip_id"]
        stop_sequence = int(row["stop_sequence"])
        if trip_id != current_trip_id:
            if current_trip_id and first_departure is not None and current_trip_id in trips_by_id:
                trip = trips_by_id[current_trip_id]
                departures_by_route_service[(trip["route_id"], trip["service_id"])].append(first_departure)
            current_trip_id = trip_id
            first_departure = parse_gtfs_time(row["departure_time"]) if stop_sequence == 1 else None
        elif stop_sequence == 1 and first_departure is None:
            first_departure = parse_gtfs_time(row["departure_time"])

    if current_trip_id and first_departure is not None and current_trip_id in trips_by_id:
        trip = trips_by_id[current_trip_id]
        departures_by_route_service[(trip["route_id"], trip["service_id"])].append(first_departure)

    waits_by_route: Dict[str, List[float]] = defaultdict(list)
    for (route_id, _service_id), departures in departures_by_route_service.items():
        departures = sorted(set(departures))
        gaps = [
            (departures[i + 1] - departures[i]) / 60.0
            for i in range(len(departures) - 1)
            if 2 * 60 <= departures[i + 1] - departures[i] <= 30 * 60
        ]
        if gaps:
            waits_by_route[route_id].append(statistics.median(gaps) / 2.0)

    route_waits: Dict[str, float] = {}
    for route_id, waits in waits_by_route.items():
        route_waits[route_id] = round(clamp(statistics.median(waits), 1.5, 8.0), 2)
    return route_waits


def build_graph(
    stations: list,
    station_index_by_id: Dict[str, int],
    stop_to_complex: Dict[str, str],
    trips_by_id: dict,
    route_styles: dict,
    route_waits: Dict[str, float],
    config: dict,
) -> Tuple[list, list, list]:
    included_route_ids = set(route_styles)
    durations_by_edge: Dict[Tuple[int, int, str], List[float]] = defaultdict(list)
    current_trip_id = None
    current_rows: List[dict] = []

    def process_trip(trip_id: str, rows: List[dict]) -> None:
        trip = trips_by_id.get(trip_id)
        if not trip or len(rows) < 2:
            return
        route_id = trip["route_id"]
        if route_id not in included_route_ids:
            return
        ordered = sorted(rows, key=lambda row: int(row["stop_sequence"]))
        for row in ordered:
            stop_id = row["stop_id"]
            complex_id = stop_to_complex.get(stop_id)
            if complex_id in station_index_by_id:
                stations[station_index_by_id[complex_id]]["routes"].add(route_id)
        for prev, nxt in zip(ordered, ordered[1:]):
            from_complex = stop_to_complex.get(prev["stop_id"])
            to_complex = stop_to_complex.get(nxt["stop_id"])
            if not from_complex or not to_complex or from_complex == to_complex:
                continue
            if from_complex not in station_index_by_id or to_complex not in station_index_by_id:
                continue
            duration_seconds = parse_gtfs_time(nxt["arrival_time"]) - parse_gtfs_time(prev["departure_time"])
            if 20 <= duration_seconds <= 1800:
                from_index = station_index_by_id[from_complex]
                to_index = station_index_by_id[to_complex]
                durations_by_edge[(from_index, to_index, route_id)].append(duration_seconds / 60.0)

    for row in read_csv_from_zip(transit_config(config)["gtfs_path"], "stop_times.txt"):
        trip_id = row["trip_id"]
        if current_trip_id is None:
            current_trip_id = trip_id
        if trip_id != current_trip_id:
            process_trip(current_trip_id, current_rows)
            current_trip_id = trip_id
            current_rows = []
        current_rows.append(row)
    if current_trip_id and current_rows:
        process_trip(current_trip_id, current_rows)

    route_states = []
    state_index_by_key: Dict[Tuple[int, str], int] = {}
    station_states: List[List[int]] = [[] for _ in stations]
    for station_index, station in enumerate(stations):
        station["routes"].intersection_update(included_route_ids)
        for route_id in sorted(station["routes"]):
            state_index_by_key[(station_index, route_id)] = len(route_states)
            route_states.append({"stationIndex": station_index, "routeId": route_id})
            station_states[station_index].append(state_index_by_key[(station_index, route_id)])

    adjacency = [dict() for _ in route_states]
    for (from_station, to_station, route_id), durations in durations_by_edge.items():
        from_state = state_index_by_key.get((from_station, route_id))
        to_state = state_index_by_key.get((to_station, route_id))
        if from_state is None or to_state is None:
            continue
        weight = round(statistics.median(durations), 2)
        existing = adjacency[from_state].get(to_state)
        if existing is None or weight < existing:
            adjacency[from_state][to_state] = weight

    for station_index, state_indexes in enumerate(station_states):
        for from_state in state_indexes:
            for to_state in state_indexes:
                if from_state == to_state:
                    continue
                to_route = route_states[to_state]["routeId"]
                transfer_cost = round(TRANSFER_PENALTY + route_waits.get(to_route, DEFAULT_BOARD_WAIT), 2)
                existing = adjacency[from_state].get(to_state)
                if existing is None or transfer_cost < existing:
                    adjacency[from_state][to_state] = transfer_cost

    for i, source in enumerate(stations):
        sx, sy = source["point"]
        for j in range(i + 1, len(stations)):
            tx, ty = stations[j]["point"]
            distance = math.hypot(tx - sx, ty - sy)
            if distance > INTER_COMPLEX_WALK_RADIUS:
                continue
            walk_minutes = distance / WALK_METERS_PER_MINUTE + INTER_COMPLEX_WALK_PENALTY
            for from_state in station_states[i]:
                for to_state in station_states[j]:
                    to_route = route_states[to_state]["routeId"]
                    from_route = route_states[from_state]["routeId"]
                    forward_cost = round(
                        walk_minutes + INTER_COMPLEX_TRANSFER_PENALTY + route_waits.get(to_route, DEFAULT_BOARD_WAIT),
                        2,
                    )
                    backward_cost = round(
                        walk_minutes + INTER_COMPLEX_TRANSFER_PENALTY + route_waits.get(from_route, DEFAULT_BOARD_WAIT),
                        2,
                    )
                    existing_forward = adjacency[from_state].get(to_state)
                    existing_backward = adjacency[to_state].get(from_state)
                    if existing_forward is None or forward_cost < existing_forward:
                        adjacency[from_state][to_state] = forward_cost
                    if existing_backward is None or backward_cost < existing_backward:
                        adjacency[to_state][from_state] = backward_cost

    return (
        route_states,
        station_states,
        [
            [[to_index, weight] for to_index, weight in sorted(edges.items())]
            for edges in adjacency
        ],
    )


def add_staten_island_ferry(
    stations: list,
    station_index_by_id: Dict[str, int],
    route_styles: Dict[str, dict],
    route_shapes: list,
    route_waits: Dict[str, float],
    route_states: list,
    station_states: List[List[int]],
    adjacency: list,
) -> None:
    st_george_id, whitehall_id = STATEN_ISLAND_FERRY_TERMINALS
    st_george_index = station_index_by_id.get(st_george_id)
    whitehall_index = station_index_by_id.get(whitehall_id)
    if st_george_index is None or whitehall_index is None:
        return

    route_styles[STATEN_ISLAND_FERRY_ROUTE_ID] = {
        "color": "#4FB3BF",
        "textColor": "#FFFFFF",
        "label": "Ferry",
    }
    route_waits[STATEN_ISLAND_FERRY_ROUTE_ID] = STATEN_ISLAND_FERRY_WAIT

    stations[st_george_index]["routes"].add(STATEN_ISLAND_FERRY_ROUTE_ID)
    stations[whitehall_index]["routes"].add(STATEN_ISLAND_FERRY_ROUTE_ID)

    start = stations[st_george_index]["point"]
    end = stations[whitehall_index]["point"]
    route_shapes.append(
        {
            "routeId": STATEN_ISLAND_FERRY_ROUTE_ID,
            "color": route_styles[STATEN_ISLAND_FERRY_ROUTE_ID]["color"],
            "textColor": route_styles[STATEN_ISLAND_FERRY_ROUTE_ID]["textColor"],
            "label": route_styles[STATEN_ISLAND_FERRY_ROUTE_ID]["label"],
            "points": round_path([start, end]),
        }
    )

    st_george_state = len(route_states)
    route_states.append({"stationIndex": st_george_index, "routeId": STATEN_ISLAND_FERRY_ROUTE_ID})
    adjacency.append([])
    station_states[st_george_index].append(st_george_state)

    whitehall_state = len(route_states)
    route_states.append({"stationIndex": whitehall_index, "routeId": STATEN_ISLAND_FERRY_ROUTE_ID})
    adjacency.append([])
    station_states[whitehall_index].append(whitehall_state)

    def upsert_edge(from_state: int, to_state: int, weight: float) -> None:
        for edge in adjacency[from_state]:
            if edge[0] == to_state:
                edge[1] = min(edge[1], weight)
                return
        adjacency[from_state].append([to_state, weight])

    travel = round(STATEN_ISLAND_FERRY_TRAVEL_MINUTES, 2)
    upsert_edge(st_george_state, whitehall_state, travel)
    upsert_edge(whitehall_state, st_george_state, travel)

    for station_index, ferry_state in ((st_george_index, st_george_state), (whitehall_index, whitehall_state)):
        for other_state in station_states[station_index]:
            if other_state == ferry_state:
                continue
            other_route = route_states[other_state]["routeId"]
            to_other = round(TRANSFER_PENALTY + route_waits.get(other_route, DEFAULT_BOARD_WAIT), 2)
            to_ferry = round(TRANSFER_PENALTY + route_waits.get(STATEN_ISLAND_FERRY_ROUTE_ID, DEFAULT_BOARD_WAIT), 2)
            upsert_edge(ferry_state, other_state, to_other)
            upsert_edge(other_state, ferry_state, to_ferry)


def build_grid_cells(polygons: MultiPolygon, stations: list, bbox: Tuple[float, float, float, float]) -> Tuple[list, list]:
    min_x, min_y, max_x, max_y = bbox
    cell_w = (max_x - min_x) / GRID_COLS
    cell_h = (max_y - min_y) / GRID_ROWS
    mask = []
    cells = []
    station_points = [station["point"] for station in stations]
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x = min_x + (col + 0.5) * cell_w
            y = min_y + (row + 0.5) * cell_h
            point = (x, y)
            if not point_in_multipolygon(point, polygons):
                mask.append(-1)
                continue
            ranked = sorted(
                (
                    (
                        station_index,
                        round(
                            math.hypot(station_point[0] - x, station_point[1] - y) / ACCESS_WALK_METERS_PER_MINUTE
                            + STATION_ACCESS_PENALTY,
                            2,
                        ),
                    )
                    for station_index, station_point in enumerate(station_points)
                ),
                key=lambda item: item[1],
            )[:CELL_NEAREST_STATIONS]
            cells.append(
                {
                    "col": col,
                    "row": row,
                    "point": round_point(point),
                    "access": [[station_index, walk_minutes] for station_index, walk_minutes in ranked],
                }
            )
            mask.append(len(cells) - 1)
    return cells, mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact data assets for the commute-time website.")
    parser.add_argument("--city", choices=sorted(LOCATION_CONFIGS), default="nyc")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = LOCATION_CONFIGS[args.city]

    ensure_source_data(config)

    area_payload = load_json(coverage_config(config)["areas_path"])
    lat0 = average_area_latitude(area_payload)
    areas, all_polygons = extract_areas(area_payload, lat0, config)
    if not areas:
        raise ValueError(f"No map areas found for {config['slug']}")
    bbox = bounds_of_multipolygon(all_polygons)
    land_polygons = all_polygons
    land_areas_path = coverage_config(config).get("land_areas_path")
    if land_areas_path:
        land_payload = load_json(land_areas_path)
        land_polygons = extract_land_mask(land_payload, lat0, bbox)
        if not land_polygons:
            raise ValueError(f"No land mask polygons found for {config['slug']}")
    min_lon, min_lat = xy_to_lonlat((bbox[0], bbox[1]), lat0)
    max_lon, max_lat = xy_to_lonlat((bbox[2], bbox[3]), lat0)
    ensure_context_data(config, (min_lon, min_lat, max_lon, max_lat))

    external_land = build_external_land_polygons(lat0, bbox, all_polygons, config)
    parks = extract_parks(lat0, bbox, config)
    streets = extract_streets(lat0, bbox, config)
    route_styles, route_shapes, trips_by_id = build_routes_and_shapes(lat0, bbox, config)
    if transit_config(config)["station_source"] == "gtfs_parent_stations":
        stations, station_index_by_id, stop_to_complex = build_gtfs_parent_station_data(config, trips_by_id, lat0)
    else:
        stations, station_index_by_id, stop_to_complex = build_nyc_station_data(lat0, config)
    route_waits = build_route_waits(trips_by_id, config)
    route_states, station_states, adjacency = build_graph(
        stations, station_index_by_id, stop_to_complex, trips_by_id, route_styles, route_waits, config
    )
    if hooks_config(config).get("manual_connection") == "staten_island_ferry":
        add_staten_island_ferry(
            stations,
            station_index_by_id,
            route_styles,
            route_shapes,
            route_waits,
            route_states,
            station_states,
            adjacency,
        )
    cells, mask = build_grid_cells(land_polygons, stations, bbox)
    ui = ui_config(config)

    output = {
        "meta": {
            "city": config["slug"],
            "displayName": config["display_name"],
            "shortName": config["short_name"],
            "areaKind": config["area_kind"],
            "searchQuerySuffix": ui["search_query_suffix"],
            "searchViewbox": ui["search_viewbox"],
            "shareText": ui["share_text"],
            "dataCredits": ui["data_credits"],
            "downloadPrefix": ui["download_prefix"],
            "urlLabel": ui["url_label"],
            "lat0": round(lat0, 6),
            "bounds": [round(value, 1) for value in bbox],
            "gridCols": GRID_COLS,
            "gridRows": GRID_ROWS,
            "walkMetersPerMinute": WALK_METERS_PER_MINUTE,
            "accessWalkMetersPerMinute": ACCESS_WALK_METERS_PER_MINUTE,
            "stationAccessPenalty": STATION_ACCESS_PENALTY,
            "originStationCount": ORIGIN_NEAREST_STATIONS,
            "cellNearestStations": CELL_NEAREST_STATIONS,
            "defaultBoardWait": DEFAULT_BOARD_WAIT,
            "transferPenalty": TRANSFER_PENALTY,
            "interComplexTransferPenalty": INTER_COMPLEX_TRANSFER_PENALTY,
        },
        "areas": areas,
        "boroughs": areas,
        "externalLand": external_land,
        "landMask": [[round_path(ring) for ring in polygon] for polygon in land_polygons]
        if land_polygons is not all_polygons
        else [],
        "parks": parks,
        "streets": streets,
        "routes": route_shapes,
        "stations": [
            {
                "id": station["id"],
                "name": station["name"],
                "point": round_point(station["point"]),
                "routes": sorted(station["routes"]),
            }
            for station in stations
        ],
        "routeStates": route_states,
        "stationStates": station_states,
        "routeWaits": route_waits,
        "adjacency": adjacency,
        "cells": cells,
        "mask": mask,
        "routeStyles": route_styles,
    }

    output_path = config["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    if config["slug"] == "nyc":
        city_output_path = config["city_output_path"]
        city_output_path.parent.mkdir(parents=True, exist_ok=True)
        city_output_path.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
