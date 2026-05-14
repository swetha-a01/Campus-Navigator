University Map Routing with Ant Colony Optimization (VIT Vellore)
=================================================================

What this is
------------
A small Python project that demonstrates Ant Colony Optimization (ACO) for campus routing. It ships with a simplified VIT Vellore outdoor graph and a Streamlit UI to compare ACO against Dijkstra.

Quick start
-----------
1) Install deps (prefer venv):
   ```
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```
2) Run the interactive demo:
   ```
   streamlit run src/app.py
   ```
   A browser tab will let you pick start/end points, pick a scenario (normal, peak-hour congestion, or blocked edge), and plot both ACO and Dijkstra routes.

Repo layout
-----------
- `data/vit_graph.json` – toy campus graph (nodes with lat/lon, edges with distance meters).
- `src/aco.py` – ACO solver for single-source/single-target routing.
- `src/baseline.py` – Dijkstra baseline using NetworkX.
- `src/graph_loader.py` – Load graph + apply scenario-specific edge penalties/closures.
- `src/app.py` – Streamlit UI.
- `src/utils.py` – Helper to compute path length/time.

How ACO is configured here
--------------------------
- Pheromone/heuristic rule: P(i→j) ∝ (τ_ij^α)(η_ij^β) with η = 1 / edge_cost.
- Defaults: ants = |V|, iterations = 60, α=1, β=3, ρ=0.5, τ0=1, Q=100.
- Elitist deposit on best-so-far path; pheromone bounded between τ_min and τ_max to reduce stagnation.

Scenarios to showcase adaptability
----------------------------------
- Normal: base distances only.
- Peak hour: congestion penalty on selected central paths.
- Blocked: one edge (near TT) removed to mimic construction/closure.

Extending
---------
- Refine the graph with real coordinates or multiple floors.
- Add multi-criteria costs (shade, stairs, indoors).
- Log convergence curves to a CSV and plot them for your report.
- Swap Streamlit for a mobile-friendly frontend if needed.

License
-------
MIT
