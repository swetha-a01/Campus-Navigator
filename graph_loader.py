"""
graph_loader.py
---------------
Loads the custom VIT campus graph from vit_graph.json into a NetworkX graph.
Does NOT require OSM / osmnx. Works fully offline.
"""
import json
import math
import pathlib
import networkx as nx

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
GRAPH_JSON = BASE_DIR / "data" / "vit_graph.json"


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Return distance in metres between two lat/lon points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl   = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_campus_graph(json_path: str | pathlib.Path = GRAPH_JSON) -> nx.Graph:
    """
    Return an undirected NetworkX Graph built from vit_graph.json.
    Each node carries: id, name, lat, lon (y=lat, x=lon for pydeck compat).
    Each edge carries: weight (metres), distance (same).
    """
    with open(json_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    G = nx.Graph()

    node_lookup: dict[str, dict] = {}
    for node in data["nodes"]:
        nid = node["id"]
        node_lookup[nid] = node
        G.add_node(nid,
                   name=node.get("name", nid),
                   lat=node["lat"], lon=node["lon"],
                   y=node["lat"],  x=node["lon"])

    for edge in data["edges"]:
        src, tgt = edge["source"], edge["target"]
        if src not in G or tgt not in G:
            continue
        # prefer explicit distance; fall back to haversine
        dist = edge.get("distance_m")
        if dist is None:
            n1, n2 = node_lookup[src], node_lookup[tgt]
            dist = _haversine(n1["lat"], n1["lon"], n2["lat"], n2["lon"])
        G.add_edge(src, tgt,
                   weight=float(dist),
                   distance=float(dist),
                   path=edge.get("path"))

    return G


def load_pois(json_path: str | pathlib.Path = GRAPH_JSON) -> list[dict]:
    """Return the raw node list from JSON (used as POIs), excluding hidden junction nodes."""
    with open(json_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    # Exclude internal routing junctions so user only sees actual destinations!
    valid_pois = []
    for node in data.get("nodes", []):
        nid = node.get("id", "")
        if not (nid.startswith("jn_") or nid.startswith("osm_")):
            valid_pois.append(node)
    
    return valid_pois