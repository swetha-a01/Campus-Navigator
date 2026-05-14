"""
aco.py – Ant Colony Optimization for campus navigation.
Works with nx.Graph (undirected, simple) or nx.MultiDiGraph (OSM).
"""
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from utils import path_length, get_edge_weight


# ── Geo helpers ───────────────────────────────────────────────────────────────

def _geo_dist_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _node_latlon(G: nx.Graph, n) -> Tuple[float, float]:
    d = G.nodes[n]
    return d.get("lat", d.get("y", 0.0)), d.get("lon", d.get("x", 0.0))


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ACOResult:
    best_path:   List  = field(default_factory=list)
    best_length: float = math.inf
    history:     List[float] = field(default_factory=list)


# ── Probabilistic selection ───────────────────────────────────────────────────

def _choice(probs: List[float]) -> int:
    total = sum(probs)
    if total == 0:
        return random.randrange(len(probs))
    r, cum = random.random() * total, 0.0
    for i, p in enumerate(probs):
        cum += p
        if r <= cum:
            return i
    return len(probs) - 1


# ── Single ant path construction ──────────────────────────────────────────────

def construct_path(
    G: nx.Graph,
    tau: Dict[tuple, float],
    alpha: float,
    beta: float,
    source,
    target,
    max_steps: int,
    target_bias: float,
) -> Tuple[List, float]:
    current  = source
    visited  = {source}
    path     = [source]
    length   = 0.0
    t_lat, t_lon = _node_latlon(G, target)

    for _ in range(max_steps):
        neighbors = list(G.neighbors(current))
        if not neighbors:
            break

        candidates = [n for n in neighbors if n not in visited] or neighbors
        weights    = []
        for nbr in candidates:
            edge_key = tuple(sorted((current, nbr)))   # undirected key
            pher     = tau.get(edge_key, 1.0) ** alpha
            ew       = get_edge_weight(G, current, nbr)
            n_lat, n_lon = _node_latlon(G, nbr)
            dist_to_goal = _geo_dist_m(n_lat, n_lon, t_lat, t_lon)
            heuristic    = 1.0 / (ew + target_bias * dist_to_goal + 1e-9)
            weights.append(pher * (heuristic ** beta))

        if not any(w > 0 for w in weights):
            break

        nxt = candidates[_choice(weights)]
        length += get_edge_weight(G, current, nxt)
        current = nxt
        path.append(current)
        visited.add(current)

        if current == target:
            return path, length

    return path, math.inf


# ── Main ACO routine ──────────────────────────────────────────────────────────

def run_aco(
    G: nx.Graph,
    source,
    target,
    iterations:  int   = 80,
    alpha:       float = 1.0,
    beta:        float = 5.0,
    rho:         float = 0.30,
    q:           float = 500.0,
    num_ants:    Optional[int] = None,
    tau_min:     float = 0.01,
    tau_max:     float = 15.0,
    target_bias: float = 0.8,
    seed:        Optional[int] = None,
) -> ACOResult:
    """Run ACO and return the best path found."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if num_ants is None:
        num_ants = max(15, min(50, G.number_of_nodes()))

    max_steps = 3 * G.number_of_nodes()

    # Initialise pheromone on every undirected edge
    tau: Dict[tuple, float] = {
        tuple(sorted(e)): 1.0 for e in G.edges()
    }

    result = ACOResult()

    for _ in range(iterations):
        successes: List[Tuple[List, float]] = []

        for _ in range(num_ants):
            path, length = construct_path(
                G, tau, alpha, beta, source, target, max_steps, target_bias
            )
            if length < math.inf:
                successes.append((path, length))
                if length < result.best_length:
                    result.best_path   = path
                    result.best_length = length

        # Evaporation
        for k in tau:
            tau[k] *= (1 - rho)

        # Pheromone deposit
        for path, length in successes:
            dep = q / length
            for u, v in zip(path, path[1:]):
                k = tuple(sorted((u, v)))
                tau[k] = min(tau_max, tau.get(k, 0) + dep)

        # Elitist reinforcement on global best
        if result.best_path:
            elite_dep = q / result.best_length
            for u, v in zip(result.best_path, result.best_path[1:]):
                k = tuple(sorted((u, v)))
                tau[k] = min(tau_max, tau.get(k, 0) + elite_dep)

        # Clamp
        for k in tau:
            tau[k] = max(tau_min, min(tau_max, tau[k]))

        result.history.append(result.best_length)

    return result
