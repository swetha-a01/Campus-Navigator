"""
app.py  –  VIT Vellore Campus Navigator
Google-Maps-style white theme + Ant Colony Optimization shortest path

Key design decisions:
 - Map is ALWAYS visible (session_state keeps routes between re-runs)
 - Paths strictly follow road/footpath edges (no straight-line shortcuts)
 - Small, clean labels - not overwhelming
 - Google Maps feel: white basemap, familiar colour coding
"""

import pathlib
import sys
import time
import math
import itertools

import networkx as nx
import pandas as pd
import pydeck as pdk
import streamlit as st

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from graph_loader import load_campus_graph, load_pois    # noqa: E402
from aco import run_aco                                   # noqa: E402
from utils import path_length, travel_time_seconds        # noqa: E402
from sjt_data import (                                     # noqa: E402
    FLOORS, LIFTS, STAIRS, WASHROOMS, ENTRANCE,
    get_navigation_steps, validate_room, room_position,
    get_wing, get_floor_key, get_rooms_for_floor,
)

# ── Constants ────────────────────────────────────────────────────────────────
MAP_STYLE    = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

# Campus map palette (Dark theme: deep blues and purples)
COL_ROAD     = [45, 55, 72, 140]      # Dark slate gray
COL_ALT      = [99, 102, 241, 160]    # Indigo blue
COL_ACO      = [139, 92, 246, 255]    # Purple
COL_START    = [99, 102, 241, 255]    # Indigo blue
COL_END      = [30, 41, 59, 255]      # Dark slate
COL_POI      = [139, 92, 246, 200]    # Purple
COL_TEXT     = [226, 232, 240]        # Light gray

# campus bounding box (VIT Vellore main campus)
CAMPUS_CENTER_LAT = 12.9700
CAMPUS_CENTER_LON = 79.1560
CAMPUS_ZOOM       = 16.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def node_pos(G: nx.Graph, n):
    d = G.nodes[n]
    return d.get("lat", d.get("y", 0.0)), d.get("lon", d.get("x", 0.0))


def edge_road_coords(G: nx.Graph, u, v):
    """
    Return road-following [[lon,lat],...] for edge u→v.
    Uses stored 'path' if available, else straight node-to-node
    (which should still be a short road segment).
    """
    edata = G.edges[u, v]
    stored = edata.get("path")
    if stored and len(stored) >= 2:
        # stored as [[lon, lat], ...] already
        return stored
    # fallback: direct segment between node centroids
    lat1, lon1 = node_pos(G, u)
    lat2, lon2 = node_pos(G, v)
    return [[lon1, lat1], [lon2, lat2]]


def path_to_polyline(G: nx.Graph, path: list):
    """Chain edge road-coords into one continuous [[lon,lat],...] polyline."""
    coords = []
    for u, v in zip(path, path[1:]):
        seg = edge_road_coords(G, u, v)
        if not coords:
            coords.extend(seg)
        else:
            # skip duplicate join point
            coords.extend(seg[1:])
    return coords


def find_all_simple_paths(G, src, tgt, cutoff=7, max_paths=12):
    paths = []
    try:
        gen = nx.all_simple_paths(G, src, tgt, cutoff=cutoff)
        for p in itertools.islice(gen, max_paths):
            paths.append(list(p))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass
    return paths


# ── Map builder ───────────────────────────────────────────────────────────────

def build_deck(
    G: nx.Graph,
    pois: list,
    src_id: str,
    tgt_id: str,
    all_paths: list,
    aco_path:  list,
    show_all: bool,
    show_labels: bool,
    is_computed: bool,
):
    layers = []

    # ── Layer 1: full road network (grey) ──────────────────────────────
    # Only show roads when routes are computed, as requested by user
    if is_computed:
        roads = []
        for u, v in G.edges():
            roads.append({"path": edge_road_coords(G, u, v)})
        layers.append(pdk.Layer(
            "PathLayer",
            data=roads,
            get_path="path",
            get_color=COL_ROAD,
            get_width=2,
            width_min_pixels=1,
            pickable=False,
        ))

    # ── Layer 2: alternate paths (blue, thin) ─────────────────────────
    if show_all and all_paths and is_computed:
        alt_rows = []
        for p in all_paths:
            if p == aco_path:
                continue
            line = path_to_polyline(G, p)
            if len(line) >= 2:
                d = path_length(G, p)
                alt_rows.append({
                    "path": line,
                    "tooltip": f"Alt route | {d:.0f} m",
                })
        if alt_rows:
            layers.append(pdk.Layer(
                "PathLayer",
                data=alt_rows,
                get_path="path",
                get_color=COL_ALT,
                get_width=4,
                width_min_pixels=2,
                pickable=True,
            ))

    # ── Layer 4: ACO path (red, thick) ─────────
    if aco_path and len(aco_path) > 1:
        a = path_length(G, aco_path)
        layers.append(pdk.Layer(
            "PathLayer",
            data=[{"path": path_to_polyline(G, aco_path),
                   "tooltip": f"Best route | {a:.0f} m"}],
            get_path="path",
            get_color=COL_ACO,
            get_width=5,
            width_min_pixels=3,
            pickable=True,
        ))

    # ── Determine labels to show ──────────────────────────────────────
    # If computed: show only elements in the optimal path (aco_path)
    if is_computed and aco_path:
        label_whitelist = set(aco_path)
        # Also always include source and target (just in case they are disconnected)
        label_whitelist.add(src_id)
        label_whitelist.add(tgt_id)
    else:
        # Keep map simple before computation: only show Start and End selections
        label_whitelist = {src_id, tgt_id}

    # ── Layer 5: POI scatter dots ─────────────────────────────────────
    poi_rows = []
    label_rows = []
    
    for p in pois:
        pid = p["id"]
        # Ensure we ONLY render dots that are supposed to be visible (start/end or routing path)!
        if pid not in label_whitelist:
            continue
            
        if pid == src_id:
            col, r = COL_START, 16  # Made smaller
        elif pid == tgt_id:
            col, r = COL_END, 16    # Made smaller
        else:
            col, r = COL_POI, 5     # Made much smaller
            
        poi_data = {
            "pos":  [p["lon"], p["lat"]],
            "name": p["name"],
            "color": col,
            "radius": r,
        }
        poi_rows.append(poi_data)
        
        # Add to labels
        if show_labels and pid in label_whitelist:
            label_rows.append(poi_data)

    if poi_rows:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=poi_rows,
            get_position="pos",
            get_fill_color="color",
            get_radius="radius",
            pickable=True,
            auto_highlight=True,
        ))

    # ── Layer 6: POI labels (small, clean) ────────────────────────────
    if label_rows:
        # white background pill first (halo)
        layers.append(pdk.Layer(
            "TextLayer",
            data=label_rows,
            get_position="pos",
            get_text="name",
            get_size=12,
            size_scale=1,
            get_color=[10, 10, 15, 255],
            get_pixel_offset=[0, -15],
            font_weight=600,
        ))
        # dark text on top
        layers.append(pdk.Layer(
            "TextLayer",
            data=label_rows,
            get_position="pos",
            get_text="name",
            get_size=12,
            size_scale=1,
            get_color=COL_TEXT,
            get_pixel_offset=[0, -15],
        ))

    # ── Layer 7: Start / End badge ────────────────────────────────────
    badges = []
    for p in pois:
        if p["id"] == src_id and is_computed:
            badges.append({"pos": [p["lon"], p["lat"]], "text": "START"})
        elif p["id"] == tgt_id and is_computed:
            badges.append({"pos": [p["lon"], p["lat"]], "text": "END"})
    if badges:
        layers.append(pdk.Layer(
            "TextLayer",
            data=badges,
            get_position="pos",
            get_text="text",
            get_size=14,
            size_scale=1,
            get_color=[240, 240, 255],
            get_background_color=[139, 92, 246, 210],
            background=True,
            get_pixel_offset=[0, -32],
        ))

    # ── View state: strictly campus ──────────────────────────
    view = pdk.ViewState(
        latitude=CAMPUS_CENTER_LAT,
        longitude=CAMPUS_CENTER_LON,
        zoom=CAMPUS_ZOOM,
        min_zoom=14,
        max_zoom=19,
        pitch=0,        # top-down like Google Maps
        bearing=0,
        transition_duration=1200,
        transition_interpolator=pdk.types.String("FlyToInterpolator"),
    )

    return pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style=MAP_STYLE,
        tooltip={
            "html": "{tooltip}<br/><b>{name}</b>",
            "style": {
                "background":   "rgba(15, 23, 42, 0.95)",
                "color":        "#e2e8f0",
                "fontSize":     "13px",
                "border":       "1px solid rgba(71, 85, 105, 0.5)",
                "borderRadius": "10px",
                "padding":      "8px 12px",
                "boxShadow":    "0 8px 26px rgba(0, 0, 0, 0.3)",
                "fontFamily":   "'Manrope', sans-serif"
            },
        },
    )


# ── Streamlit UI ─────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="VIT Vellore Campus Navigator",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── CSS ────────────────────────────────────────────────────────────
    st.markdown("""
    
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Manrope:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

:root {
    --paper: #0f172a;
    --paper-2: #1e293b;
    --ink: #e2e8f0;
    --muted: #94a3b8;
    --accent: #6366f1;
    --accent-2: #4f46e5;
    --accent-3: #8b5cf6;
    --border: rgba(71, 85, 105, 0.3);
    --shadow: 0 10px 28px rgba(0, 0, 0, 0.3);
    --wash: rgba(30, 41, 59, 0.8);
}

[data-testid="stAppViewContainer"] {
    background-color: var(--paper);
    background-image:
        radial-gradient(800px 400px at 10% -10%, rgba(139, 92, 246, 0.15), transparent 60%),
        radial-gradient(700px 420px at 95% 0%, rgba(99, 102, 241, 0.18), transparent 60%),
        repeating-linear-gradient(0deg, rgba(30, 41, 59, 0.1), rgba(30, 41, 59, 0.1) 1px, transparent 1px, transparent 24px),
        repeating-linear-gradient(90deg, rgba(30, 41, 59, 0.08), rgba(30, 41, 59, 0.08) 1px, transparent 1px, transparent 24px);
    background-size: auto, auto, auto, auto;
    font-family: 'Manrope', sans-serif;
    color: var(--ink);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid var(--border);
    box-shadow: 6px 0 24px rgba(0, 0, 0, 0.2);
}

.main .block-container {
    padding-top: 5.2rem !important;
    padding-bottom: 1.5rem;
    max-width: 1400px;
}

.vitnav-header {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 3.8rem;
    z-index: 999990;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    background: rgba(15, 23, 42, 0.95);
    border-bottom: 1px solid var(--border);
    box-shadow: var(--shadow);
    backdrop-filter: blur(6px);
}
.vitnav-header .badge {
    background: #6366f1;
    color: #e2e8f0;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 0.68rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
}
.vitnav-header h1 {
    margin: 0;
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: 0.2px;
    color: #e2e8f0;
    font-family: 'Fraunces', serif;
}
.vitnav-header .sub {
    border-left: 1px solid rgba(71, 85, 105, 0.4);
    padding-left: 12px;
    margin-left: 4px;
    font-size: 0.78rem;
    color: var(--muted);
    letter-spacing: 0.8px;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border: 1px solid rgba(71, 85, 105, 0.4);
    color: #e2e8f0;
    font-weight: 700;
    letter-spacing: 0.2px;
    border-radius: 10px;
    padding: 0.6rem 1.1rem;
    box-shadow: 0 10px 24px rgba(99, 102, 241, 0.3);
    transition: all 0.25s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 30px rgba(99, 102, 241, 0.4);
}

/* Inputs */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input, .stSlider > div {
    background: var(--wash) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--ink) !important;
}

.stSelectbox label, .stSlider label, .stCheckbox label, .stNumberInput label, .stTextInput label,
.stCheckbox p, .stCheckbox span, [data-testid="stCheckbox"] p {
    color: var(--muted) !important;
    font-family: 'Manrope', sans-serif;
    font-size: 0.95rem;
    letter-spacing: 0.2px;
    font-weight: 500;
}

.stTextInput label {
    color: #e2e8f0 !important;
    font-size: 1.1rem !important;
}

.stSlider {
    margin-bottom: 1rem !important;
}

[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #e2e8f0 !important;
    font-family: 'Fraunces', serif;
    font-weight: 700;
}

/* Hide native chrome */
[data-testid="stDecoration"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Metrics */
.mcard {
    background: rgba(30, 41, 59, 0.8);
    border-radius: 14px;
    padding: 22px 26px;
    border: 1px solid var(--border);
    border-left: 4px solid;
    box-shadow: var(--shadow);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.mcard:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 30px rgba(0, 0, 0, 0.4);
}
.mcard.r { border-color: var(--accent); }
.mcard.b { border-color: var(--accent-3); }
.mcard h4 {
    margin: 0 0 8px;
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
}
.mcard .v {
    font-size: 1.9rem;
    font-weight: 700;
    color: #e2e8f0;
    font-family: 'Fraunces', serif;
}
.mcard .s {
    font-size: 0.86rem;
    color: var(--muted);
    margin-top: 6px;
}

/* SJT section */
.sjt-header {
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: var(--shadow);
}
.sjt-header h2 {
    font-family: 'Fraunces', serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: #e2e8f0;
    margin: 0 0 6px 0;
}
.sjt-header p {
    color: var(--muted);
    font-size: 0.92rem;
    margin: 0;
}

.floor-plan-wrap {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px;
    margin: 14px 0;
    box-shadow: var(--shadow);
}
.floor-plan-wrap h4 {
    font-family: 'Fraunces', serif;
    color: #e2e8f0;
    font-weight: 700;
    font-size: 0.98rem;
    margin: 0 0 14px 0;
}

.nav-step {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 14px 18px;
    margin-bottom: 8px;
    border-radius: 10px;
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid var(--border);
    transition: all 0.25s ease;
}
.nav-step:hover {
    border-color: rgba(139, 92, 246, 0.6);
    transform: translateX(4px);
}
.nav-step .step-num {
    background: #6366f1;
    color: #e2e8f0;
    width: 26px;
    height: 26px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.nav-step .step-text {
    color: #cbd5e1;
    font-size: 0.92rem;
    line-height: 1.5;
}

.room-info {
    background: rgba(30, 41, 59, 0.9);
    border-radius: 14px;
    padding: 22px 26px;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent-2);
    margin-bottom: 16px;
    box-shadow: var(--shadow);
}
.room-info h3 {
    color: #e2e8f0;
    font-size: 1.2rem;
    font-weight: 700;
    margin: 0 0 12px 0;
    font-family: 'Fraunces', serif;
}
.room-info .ri-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    color: #cbd5e1;
    font-size: 0.9rem;
}
.room-info .ri-row .ri-label {
    color: var(--muted);
    min-width: 100px;
}
.room-info .ri-row .ri-value {
    color: #e2e8f0;
    font-weight: 600;
}

.facility-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 4px;
    font-size: 0.85rem;
    color: #cbd5e1;
    transition: all 0.25s ease;
}
.facility-badge:hover {
    border-color: rgba(139, 92, 246, 0.7);
    transform: translateY(-2px);
}

.floor-indicator { display: flex; gap: 6px; margin: 12px 0; flex-wrap: wrap; }
.floor-chip {
    padding: 6px 16px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid var(--border);
    color: var(--muted);
    background: rgba(30, 41, 59, 0.8);
    transition: all 0.25s ease;
}
.floor-chip.active {
    background: #6366f1;
    color: #e2e8f0;
    border-color: transparent;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
}

.legend-container {
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: var(--shadow);
}
.leg {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 8px 0;
    color: #cbd5e1;
    font-size: 0.88rem;
}
.ld {
    width: 16px;
    height: 6px;
    border-radius: 999px;
}
</style>

    """, unsafe_allow_html=True)

    # ── Header ─────────────────────────────────────────────────────────
    st.markdown("""
    <div class="vitnav-header">
        <div class="badge">Campus Map</div>
        <h1>VIT Vellore Campus Navigator</h1>
    </div>""", unsafe_allow_html=True)

    # ── Load data once ─────────────────────────────────────────────────
    # Removed st.cache_resource so it instantly updates when JSON changes!
    def get_data():
        G    = load_campus_graph()
        pois = load_pois()
        return G, pois

    G, pois   = get_data()
    poi_ids   = [p["id"]   for p in pois]
    poi_names = {p["id"]: p["name"] for p in pois}

    # ── Session state (persist routes across re-runs) ──────────────────
    for key, default in [
        ("all_paths",     []),
        ("aco_path",      []),
        ("src_id",        ""),
        ("tgt_id",        ""),
        ("computed",      False),
        ("a_len",         0.0),
        ("elapsed",       0.0),
        ("iterations",    80),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Sidebar ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## Route Settings")
        st.markdown("---")

        src = st.selectbox(
            "Start location", poi_ids,
            format_func=lambda x: poi_names[x],
            index=poi_ids.index("main_gate") if "main_gate" in poi_ids else 0,
        )
        tgt = st.selectbox(
            "Destination", poi_ids,
            format_func=lambda x: poi_names[x],
            index=poi_ids.index("tt") if "tt" in poi_ids else 1,
        )

        st.markdown("---")
        st.markdown("### ACO Parameters")
        iterations  = st.slider("Iterations",       20, 300,  80, step=10)
        num_ants    = st.slider("Ants per iteration", 10, 80, 30, step=5)
        seed_val    = st.number_input("Random seed (0 = random)", 0, 9999, 42)
        use_seed    = int(seed_val) if seed_val != 0 else None

        st.markdown("---")
        st.markdown("### Display Options")
        max_alts    = st.slider("Max alternate paths",  2, 12, 6)
        hop_limit   = st.slider("Path search depth",    10, 40, 20)
        show_all    = st.checkbox("Show alternate paths",    value=True)
        show_labels = st.checkbox("Show location names",     value=True)

        st.markdown("---")
        find_btn = st.button("Find Routes", use_container_width=True)

        st.markdown("---")
        st.markdown("### Legend")
        st.markdown("""
        <div class="legend-container">
            <div class="leg"><div class="ld" style="background:#2d3748"></div>Campus roads</div>
            <div class="leg"><div class="ld" style="background:#6366f1;box-shadow:0 0 10px rgba(99,102,241,0.35)"></div>Alternate routes</div>
            <div class="leg"><div class="ld" style="background:#8b5cf6;box-shadow:0 0 10px rgba(139,92,246,0.35)"></div>Best route</div>
            <div class="leg"><div class="ld" style="background:#6366f1;border-radius:50%;width:10px;height:10px;box-shadow:0 0 8px rgba(99,102,241,0.35)"></div>Start point</div>
            <div class="leg"><div class="ld" style="background:#1e293b;border-radius:50%;width:10px;height:10px;box-shadow:0 0 8px rgba(30,41,59,0.35)"></div>End point</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Find routes button logic ───────────────────────────────────────
    if find_btn:
        if src == tgt:
            st.warning("Start and destination must be different.")
        else:
            with st.spinner("Computing routes along roads & footpaths…"):
                t0 = time.time()

                all_paths = find_all_simple_paths(
                    G, src, tgt, cutoff=hop_limit, max_paths=max_alts + 5
                )

                aco_res = run_aco(G, src, tgt,
                                  iterations=iterations,
                                  num_ants=num_ants,
                                  seed=use_seed)
                a_path = aco_res.best_path
                a_len  = aco_res.best_length

                t1 = time.time()

            # Save to session state
            st.session_state.all_paths     = all_paths
            st.session_state.aco_path      = a_path
            st.session_state.src_id        = src
            st.session_state.tgt_id        = tgt
            st.session_state.computed      = True
            st.session_state.a_len         = a_len
            st.session_state.elapsed       = t1 - t0
            st.session_state.iterations    = iterations

    # ── Metrics row (only after computation) ──────────────────────────
    if st.session_state.computed:
        a_len = st.session_state.a_len

        c1, c2 = st.columns(2)
        with c1:
            t2 = travel_time_seconds(a_len) / 60 if a_len < 1e9 else 0
            h2 = len(st.session_state.aco_path) - 1
            vs = f"{a_len:.0f} m" if a_len < 1e9 else "No path"
            st.markdown(f"""<div class="mcard r">
                <h4>ACO Best Path</h4>
                <div class="v">{vs}</div>
                <div class="s">~{t2:.1f} min walk | {h2} segments</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            n = len(st.session_state.all_paths)
            el = st.session_state.elapsed
            it = st.session_state.iterations
            st.markdown(f"""<div class="mcard b">
                <h4>Routes Explored</h4>
                <div class="v">{n}</div>
                <div class="s">Done in {el:.2f}s | {it} ACO iterations</div>
            </div>""", unsafe_allow_html=True)

        # Path table
        with st.expander("All Routes Breakdown", expanded=False):
            rows = []
            # Make sure ACO path is logically included even if all_paths misses it
            paths_to_show = list(st.session_state.all_paths)
            if st.session_state.aco_path and st.session_state.aco_path not in paths_to_show:
                paths_to_show.insert(0, st.session_state.aco_path)
            
            for i, p in enumerate(paths_to_show, 1):
                ln  = path_length(G, p)
                tm  = travel_time_seconds(ln) / 60
                tag = ("ACO" if p == st.session_state.aco_path else "")
                via = " -> ".join(poi_names.get(n, n) for n in p if not str(n).startswith("osm_") and not str(n).startswith("jn_"))
                rows.append({"#": i, "Route": via,
                             "Distance (m)": f"{ln:.0f}",
                             "Time (min)":   f"{tm:.1f}", "":tag})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Select Start and Destination in the sidebar, then click Find Routes.")

    # ── MAP (always rendered) ──────────────────────────────────────────
    deck = build_deck(
        G, pois,
        src_id        = st.session_state.src_id if st.session_state.computed else src,
        tgt_id        = st.session_state.tgt_id if st.session_state.computed else tgt,
        all_paths     = st.session_state.all_paths if show_all else [],
        aco_path      = st.session_state.aco_path,
        show_all      = show_all,
        show_labels   = show_labels,
        is_computed   = st.session_state.computed,
    )
    st.pydeck_chart(deck, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # ██  SJT INDOOR BLOCK NAVIGATION                                    ██
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("""<br>""", unsafe_allow_html=True)
    st.markdown("""
    <div class="sjt-header">
        <h2>SJT Block Navigator</h2>
        <p>Find any classroom inside Silver Jubilee Tower - enter a room number to get step-by-step directions, floor plan, and nearest facilities.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Room input ─────────────────────────────────────────────────
    sjt_col1, sjt_col2 = st.columns([2, 1])
    with sjt_col1:
        room_input = st.text_input(
            "Enter SJT Room Number",
            placeholder="e.g.  G07,  215,  423,  801",
            help="Ground floor: G01-G30  |  Floors 1-8: 101-830",
            key="sjt_room_input",
        )
    with sjt_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        sjt_search = st.button("Find Room", use_container_width=True, key="sjt_find_btn")

    # ── Process search ────────────────────────────────────────────
    if sjt_search and room_input:
        is_valid, msg = validate_room(room_input)
        if not is_valid:
            st.error(msg)
        else:
            nav = get_navigation_steps(room_input)
            if nav is None:
                st.error("Could not generate navigation for that room.")
            else:
                st.success(msg)

                # ── Room Info Card ─────────────────────────────────
                dept_str = ", ".join(nav["departments"])
                st.markdown(f"""
                <div class="room-info">
                    <h3>Room {nav["room"]}</h3>
                    <div class="ri-row"><span class="ri-label">Floor</span><span class="ri-value">{nav["floor_name"]} (Level {nav["floor_level"]})</span></div>
                    <div class="ri-row"><span class="ri-label">Wing</span><span class="ri-value">{nav["wing"]}</span></div>
                    <div class="ri-row"><span class="ri-label">Department</span><span class="ri-value">{dept_str}</span></div>
                </div>
                """, unsafe_allow_html=True)

                # ── Floor indicator chips ─────────────────────────
                chips_html = '<div class="floor-indicator">'
                for fk, fv in FLOORS.items():
                    active = "active" if fk == nav["floor_key"] else ""
                    chips_html += f'<div class="floor-chip {active}">{fv["name"]}</div>'
                chips_html += '</div>'
                st.markdown(chips_html, unsafe_allow_html=True)

                # ── Interactive Floor Plan (SVG) ──────────────────
                st.markdown('<div class="floor-plan-wrap">', unsafe_allow_html=True)
                st.markdown(f'<h4>Floor Plan ? {nav["floor_name"]}</h4>', unsafe_allow_html=True)
                svg = _render_floor_plan_svg(nav)
                st.markdown(svg, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # ── Nearby Facilities Badges ──────────────────────
                st.markdown("#### Nearby Facilities")
                fac_html = ""
                fac_html += f'<span class="facility-badge"><span class="fb-icon">{nav["nearest_lift"]["icon"]}</span>{nav["nearest_lift"]["name"]}</span>'
                fac_html += f'<span class="facility-badge"><span class="fb-icon">{nav["nearest_stair"]["icon"]}</span>{nav["nearest_stair"]["name"]}</span>'
                fac_html += f'<span class="facility-badge"><span class="fb-icon">{nav["nearest_washroom"]["icon"]}</span>{nav["nearest_washroom"]["name"]}</span>'
                st.markdown(fac_html, unsafe_allow_html=True)

                # ── Step-by-step Navigation ───────────────────────
                st.markdown("#### Step-by-Step Directions")
                for step in nav["steps"]:
                    st.markdown(f"""
                    <div class="nav-step">
                        <div class="step-num">{step['step']}</div>
                        <div class="step-icon">{step['icon']}</div>
                        <div class="step-text">{step['instruction']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    elif sjt_search and not room_input:
        st.warning("Please enter a room number first.")


def _render_floor_plan_svg(nav: dict) -> str:
    """
    Render an interactive SVG floor plan for the SJT block.
    Shows corridors, rooms, lifts, stairs, washrooms, and highlights the target room.
    """
    W, H = 900, 380
    target_pos = nav["position"]
    floor_key = nav["floor_key"]
    target_room = nav["room"]

    svg_parts = []
    svg_parts.append(
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;height:auto;font-family:\'Manrope\',sans-serif;">'
    )

    # ── Definitions: gradients & filters ──
    svg_parts.append(
        '<defs>'
        '<linearGradient id="gBg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#1e293b" />'
        '<stop offset="100%" stop-color="#0f172a" />'
        '</linearGradient>'
        '<linearGradient id="gCorridor" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#334155" />'
        '<stop offset="100%" stop-color="#475569" />'
        '</linearGradient>'
        '<linearGradient id="gRoom" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1e293b" />'
        '<stop offset="100%" stop-color="#0f172a" />'
        '</linearGradient>'
        '<linearGradient id="gTarget" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#7c3aed" />'
        '<stop offset="100%" stop-color="#4f46e5" />'
        '</linearGradient>'
        '<filter id="glow">'
        '<feGaussianBlur stdDeviation="4" result="bloom" />'
        '<feMerge><feMergeNode in="bloom" /><feMergeNode in="SourceGraphic" /></feMerge>'
        '</filter>'
        '<filter id="glowTarget">'
        '<feGaussianBlur stdDeviation="6" result="bloom" />'
        '<feMerge><feMergeNode in="bloom" /><feMergeNode in="SourceGraphic" /></feMerge>'
        '</filter>'
        '</defs>'
    )

    # ── Background ──
    svg_parts.append(f'<rect width="{W}" height="{H}" rx="12" fill="url(#gBg)" stroke="#334155" stroke-width="1" />')

    # ── Floor label ──
    floor_info = FLOORS.get(floor_key, {})
    svg_parts.append(f'<text x="20" y="28" fill="#94a3b8" font-size="13" font-weight="500">{floor_info.get("name", "")} — Silver Jubilee Tower</text>')

    # ── Building outline ──
    bx, by, bw, bh = 30, 50, W - 60, H - 100
    svg_parts.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" '
                     f'fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="6,3" />')

    # -- Central corridor --
    cor_y = by + bh * 0.42
    cor_h = bh * 0.16
    svg_parts.append(f'<rect x="{bx + 10}" y="{cor_y}" width="{bw - 20}" height="{cor_h}" '
                     f'rx="3" fill="url(#gCorridor)" opacity="0.5" />')
    svg_parts.append(f'<text x="{W // 2}" y="{cor_y + cor_h / 2 + 4}" '
                     f'fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="400">-- C O R R I D O R --</text>')

    # -- Wing separators --
    mid_x = bx + bw * 0.5
    svg_parts.append(f'<line x1="{mid_x}" y1="{by}" x2="{mid_x}" y2="{by + bh}" '
                     f'stroke="#4f46e5" stroke-width="1" stroke-dasharray="4,4" opacity="0.4" />')
    svg_parts.append(f'<text x="{bx + bw * 0.25}" y="{by + bh + 18}" fill="#94a3b8" font-size="10" text-anchor="middle">LEFT WING (West)</text>')
    svg_parts.append(f'<text x="{bx + bw * 0.75}" y="{by + bh + 18}" fill="#94a3b8" font-size="10" text-anchor="middle">RIGHT WING (East)</text>')

    # -- Draw rooms --
    rooms = get_rooms_for_floor(floor_key)
    room_w, room_h = 46, 34

    for room_num in rooms:
        pos = room_position(room_num)
        if pos is None:
            continue

        rx = bx + pos["x"] * bw
        ry = by + pos["y"] * bh
        is_target = room_num == target_room

        if is_target:
            # Target room: highlighted with glow
            svg_parts.append(f'<rect x="{rx - room_w / 2}" y="{ry - room_h / 2}" '
                             f'width="{room_w}" height="{room_h}" rx="5" '
                             f'fill="url(#gTarget)" stroke="#a78bfa" stroke-width="2" filter="url(#glowTarget)" />')
            svg_parts.append(f'<text x="{rx}" y="{ry + 4}" fill="#fff" font-size="11" '
                             f'text-anchor="middle" font-weight="700">{room_num}</text>')
            # Pulse ring
            svg_parts.append(f'<circle cx="{rx}" cy="{ry}" r="28" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.6">'
                             f'<animate attributeName="r" from="28" to="40" dur="1.5s" repeatCount="indefinite" />'
                             f'<animate attributeName="opacity" from="0.6" to="0" dur="1.5s" repeatCount="indefinite" />'
                             f'</circle>')
        else:
            # Normal room
            svg_parts.append(f'<rect x="{rx - room_w / 2}" y="{ry - room_h / 2}" '
                             f'width="{room_w}" height="{room_h}" rx="4" '
                             f'fill="url(#gRoom)" stroke="#334155" stroke-width="1" />')
            svg_parts.append(f'<text x="{rx}" y="{ry + 4}" fill="#64748b" font-size="9" '
                             f'text-anchor="middle" font-weight="400">{room_num}</text>')

    # ── Draw lifts ──
    for lift in LIFTS:
        lx = bx + lift["x"] * bw
        ly = by + lift["y"] * bh
        svg_parts.append(f'<rect x="{lx - 14}" y="{ly - 14}" width="28" height="28" rx="6" '
                         f'fill="#1e40af" stroke="#3b82f6" stroke-width="1.5" filter="url(#glow)" />')
        svg_parts.append(f'<text x="{lx}" y="{ly + 5}" fill="white" font-size="14" text-anchor="middle">{lift["icon"]}</text>')
        svg_parts.append(f'<text x="{lx}" y="{ly + 24}" fill="#60a5fa" font-size="8" text-anchor="middle">{lift["name"]}</text>')

    # ── Draw stairs ──
    for stair in STAIRS:
        sx = bx + stair["x"] * bw
        sy = by + stair["y"] * bh
        svg_parts.append(f'<rect x="{sx - 14}" y="{sy - 14}" width="28" height="28" rx="6" '
                         f'fill="#065f46" stroke="#10b981" stroke-width="1.5" filter="url(#glow)" />')
        svg_parts.append(f'<text x="{sx}" y="{sy + 5}" fill="white" font-size="14" text-anchor="middle">{stair["icon"]}</text>')
        svg_parts.append(f'<text x="{sx}" y="{sy + 24}" fill="#34d399" font-size="8" text-anchor="middle">{stair["name"]}</text>')

    # ── Draw washrooms ──
    for wc in WASHROOMS:
        wx = bx + wc["x"] * bw
        wy = by + wc["y"] * bh
        svg_parts.append(f'<rect x="{wx - 12}" y="{wy - 12}" width="24" height="24" rx="5" '
                         f'fill="#4a1d6a" stroke="#a855f7" stroke-width="1" />')
        svg_parts.append(f'<text x="{wx}" y="{wy + 5}" fill="white" font-size="12" text-anchor="middle">{wc["icon"]}</text>')
        svg_parts.append(f'<text x="{wx}" y="{wy + 22}" fill="#c084fc" font-size="7" text-anchor="middle">{wc["name"]}</text>')

    # ── Entrance ──
    ex = bx + ENTRANCE["x"] * bw
    ey = by + bh - 5
    svg_parts.append(f'<rect x="{ex - 30}" y="{ey - 8}" width="60" height="18" rx="4" '
                     f'fill="#7e22ce" stroke="#a78bfa" stroke-width="1" />')
    svg_parts.append(f'<text x="{ex}" y="{ey + 6}" fill="white" font-size="9" text-anchor="middle" font-weight="600">🚪 ENTRANCE</text>')

    # ── Legend ──
    leg_x, leg_y = W - 180, 50
    svg_parts.append(f'<rect x="{leg_x - 10}" y="{leg_y - 5}" width="170" height="100" rx="8" '
                     f'fill="rgba(15,23,42,0.8)" stroke="#334155" stroke-width="1" />')
    svg_parts.append(f'<text x="{leg_x}" y="{leg_y + 12}" fill="#94a3b8" font-size="9" font-weight="600">LEGEND</text>')
    legend_items = [
        ("#7c3aed", "Target Room"),
        ("#1e40af", "Lift"),
        ("#065f46", "Staircase"),
        ("#4a1d6a", "Washroom"),
    ]
    for i, (col, label) in enumerate(legend_items):
        ly = leg_y + 28 + i * 18
        svg_parts.append(f'<rect x="{leg_x}" y="{ly - 6}" width="12" height="12" rx="3" fill="{col}" />')
        svg_parts.append(f'<text x="{leg_x + 20}" y="{ly + 4}" fill="#cbd5e1" font-size="10">{label}</text>')

    svg_parts.append('</svg>')
    return "".join(svg_parts)


if __name__ == "__main__":
    main()
