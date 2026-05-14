import networkx as nx

AVG_WALK_SPEED_MPS = 1.4  # ~5 km/h


def path_length(graph: nx.Graph, path: list[str]) -> float:
    """Return total weight along a path; returns inf if path invalid."""
    if path is None or len(path) < 2:
        return float("inf")
    total = 0.0
    for u, v in zip(path, path[1:]):
        if graph.has_edge(u, v):
            total += get_edge_weight(graph, u, v)
        else:
            return float("inf")
    return total


def travel_time_seconds(distance_m: float) -> float:
    return distance_m / AVG_WALK_SPEED_MPS


def get_edge_weight(graph: nx.Graph, u, v) -> float:
    if graph.is_multigraph():
        data = graph.get_edge_data(u, v) or {}
        weights = []
        for _, ed in data.items():
            weights.append(ed.get("weight", ed.get("distance", 1.0)))
        return min(weights) if weights else float("inf")
    return graph[u][v].get("weight", graph[u][v].get("distance", float("inf")))


def get_edge_data_min(graph: nx.Graph, u, v):
    if graph.is_multigraph():
        data = graph.get_edge_data(u, v) or {}
        best = None
        best_w = float("inf")
        for _, ed in data.items():
            w = ed.get("weight", ed.get("distance", 1.0))
            if w < best_w:
                best_w = w
                best = ed
        return best or {}
    return graph[u][v]
