import pathlib
from typing import Dict, List, Tuple

import networkx as nx
import osmnx as ox
import numpy as np

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "vit_osm.graphml"


def load_osm_graph(place: str = "VIT University, Vellore, India") -> nx.Graph:
    """Load walkable OSM graph; cache locally to avoid repeated downloads."""
    if CACHE_PATH.exists():
        G = ox.load_graphml(CACHE_PATH)
    else:
        G = ox.graph_from_place(place, network_type="walk", simplify=True)
        # ensure lengths exist
        G = ox.distance.add_edge_lengths(G)
        ox.save_graphml(G, CACHE_PATH)

    # Ensure weight/distance on every edge (keep MultiDiGraph)
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", data.get("weight", 1.0))
        data["weight"] = length
        data["distance"] = length

    return G


def snap_pois_to_graph(G: nx.Graph, pois: List[dict]) -> Dict[str, int]:
    """Return mapping from poi id to nearest OSM node id (no sklearn needed)."""
    nodes = list(G.nodes(data=True))
    node_ids = [n for n, _ in nodes]
    lats = np.array([d.get('y', d.get('lat')) for _, d in nodes], dtype=float)
    lons = np.array([d.get('x', d.get('lon')) for _, d in nodes], dtype=float)
    mapping: Dict[str, int] = {}
    for poi in pois:
        dists = _haversine_np(poi['lat'], poi['lon'], lats, lons)
        idx = int(np.argmin(dists))
        mapping[poi['id']] = node_ids[idx]
    return mapping


def truncate_graph(G: nx.Graph, start_lat: float, start_lon: float, end_lat: float, end_lon: float, buffer_deg: float = 0.002) -> nx.Graph:
    """Truncate graph to a bounding box around start/end to speed up ACO."""
    north = max(start_lat, end_lat) + buffer_deg
    south = min(start_lat, end_lat) - buffer_deg
    east = max(start_lon, end_lon) + buffer_deg
    west = min(start_lon, end_lon) - buffer_deg
    try:
        return ox.truncate.truncate_graph_bbox(G, north, south, east, west, retain_all=False)
    except Exception:
        return G


def _haversine_np(lat1, lon1, lats, lons):
    r = 6371000.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lats)
    dphi = np.radians(lats - lat1)
    dl = np.radians(lons - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dl / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return r * c



def load_buildings(place: str = "VIT University, Vellore, India", force_reload: bool = False):
    """Load named buildings as GeoDataFrame with centroid lat/lon. Cached to GeoJSON."""
    cache = CACHE_PATH.with_name("vit_buildings.geojson")
    try:
        import geopandas as gpd
    except Exception:
        gpd = None

    if cache.exists() and gpd is not None and not force_reload:
        try:
            gdf = gpd.read_file(cache)
            # if cached file has no usable names, rebuild
            if "name" in gdf.columns and gdf["name"].notna().any():
                return gdf
        except Exception:
            pass

    tags = {"building": True}
    # OSMnx 2.x uses features_from_place; fall back for older versions
    if hasattr(ox, "features_from_place"):
        gdf = ox.features_from_place(place, tags)
    else:
        gdf = ox.geometries_from_place(place, tags)

    # keep only polygonal geometry
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

    # Build a name column from common alternatives
    name_cols = ["name", "name:en", "official_name", "alt_name", "short_name", "addr:housename", "addr:place"]
    for col in name_cols:
        if col not in gdf.columns:
            gdf[col] = None
    gdf["name"] = gdf[name_cols].bfill(axis=1).iloc[:, 0]
    gdf = gdf[gdf["name"].notna()]

    # centroid for label position
    gdf["lon"] = gdf.geometry.centroid.x
    gdf["lat"] = gdf.geometry.centroid.y

    if gpd is not None:
        try:
            gdf.to_file(cache, driver="GeoJSON")
        except Exception:
            pass

    return gdf
