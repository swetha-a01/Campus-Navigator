import networkx as nx
from utils import path_length


def shortest_path(graph: nx.Graph, source, target) -> tuple[list, float]:
    """Dijkstra shortest path. Returns (path, length_m)."""
    try:
        path = nx.shortest_path(graph, source=source, target=target, weight="weight")
        return path, path_length(graph, path)
    except nx.NetworkXNoPath:
        return [], float("inf")
