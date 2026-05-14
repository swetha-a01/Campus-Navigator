# 🗺️ VIT Vellore Campus Navigator: Architecture & User Guide

Welcome to the complete overview of the **VIT Vellore Campus Navigator**. This application is a high-precision, AI-driven pathfinding dashboard specifically built for the VIT Vellore campus. It breaks away from standard GPS apps by strictly adhering to a hard-coded grid of campus footpaths, roads, and walkways, guaranteeing extremely accurate, walkable routes.

---

## 1. How It Works (Under The Hood)

The entire system relies on three separate engine layers working together flawlessly:

### A. The Graph Generation (`build_graph.py`)
Instead of drawing straight lines between buildings (which might tell users to walk through lakes or solid walls), the application builds a **mathematical graph**. 
- It uses the `osmnx` library to download precise geographic road/footpath data directly from OpenStreetMap within the VIT campus bounding box.
- It calculates intersections (nodes) and the roads connecting them (edges).
- It injects your custom Point of Interest (POI) coordinates (like the Library or Woodys) and chemically "snaps" them to the nearest real-world footpath.
- It bakes all of this into `data/vit_graph.json` so the app runs offline, blazingly fast.

### B. The Routing Engine (`aco.py`)
This app does not use standard, outdated algorithms like Dijkstra's. It runs entirely on **Ant Colony Optimization (ACO)**. 
- ACO is an AI model inspired by nature. We simulate hundreds of "digital ants" traversing the VIT campus network.
- As ants stumble upon shorter routes from the Main Gate to TT, they leave "digital pheromones". 
- Subsequent ants follow the strongest pheromone trails. Over time (your iterations), the swarm converges on the absolute, mathematically optimal path. 

### C. The Frontend Dashboard (`app.py`)
The user interface is built using Streamlit, hijacked with aggressive custom CSS to override its basic layout. It utilizes a **Lunar Glassmorphic** theme rendering a map via `pydeck`, communicating with Carto's Dark Matter GL tiles.

---

## 2. Feature Breakdown & Sidebar Options

Here is exactly what every parameter on the left side of your screen does:

### ⚙️ Route Settings
*   **Start Location & Destination**: The precise coordinates injected from your custom JSON. These are the entry and exit points for the algorithms.

### 🐜 ACO Parameters (The AI Control Room)
These sliders let you modify the "brain" of the ant swarm algorithm in real-time.
*   **Iterations (Default: 80)**: How many "generations" of ants you want to send out. More iterations mean the AI has a better chance of finding a tricky shortcut, but computation slows down.
*   **Ants per iteration (Default: 30)**: How many ants are deployed into the graph at once per generation. Higher numbers mean the map is explored wider and faster.
*   **Random seed**: ACO relies on randomness to explore (just like real ants wandering). Setting a specific seed (like `42`) forces the randomness to be the same every time, ensuring you get the exact same route result for testing. Setting to `0` means true randomness.

### 🗺️ Display
*   **Max alternate paths**: While the Ants find the absolute best route, the app also forces a background search for *similar* routes. This limits how many backup routes (the cyan blue lines) render on your map.
*   **Path search depth**: Limits the complexity of alternate routes. If set to 10, the app won't search for paths that require more than 10 intersection turns.
*   **Show alternate paths & Location names**: Toggles the cyan map lines and the hovering white location tags to clean up map clutter.

---

## 3. What Changes Can Be Updated Later? (Future Roadmaps)

This application is built as a highly scalable infrastructure. Here is what can be upgraded in the future:

### A. Dynamic Traffic & Crowds
Right now, the graph edges only calculate distance (`best_length`). Later, you could add "time of day crowds" as penalties. (e.g., If it's 1:00 PM, mathematically increase the "distance" of the SJT footpaths so the AI routes you the long, uncrowded way around).

### B. Map Infrastructure Updates
IfVIT builds a new academic block or opens a new road:
1. You just open `build_graph.py`.
2. Wait for OSM to update, or manually add the coordinate.
3. Run `python build_graph.py` to overwrite `data/vit_graph.json`. The app instantly scales to the new roads without touching a single line of React or Streamlit frontend code.

### C. Geolocation (Live Tracking)
Because `pydeck` accepts Lat/Lon data natively, you could hook up HTML5 browser geolocation APIs later. Instead of users picking "Main Gate" from a dropdown, the app would drop a blue dot on their precise GPS coordinates and deploy the Ant swarm starting from their phone's location.

### D. Layer Adding (Buildings & 3D Extrusions)
Pydeck supports 3D rendering (`PolygonLayer`). You could fetch the vector footprint boundaries of TT or SMV from OpenStreetMaps and extrude them realistically out of the map using `get_elevation`, turning the 2D app into a fully 3D interactive campus model alongside the glowing paths.
