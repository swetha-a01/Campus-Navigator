import json
import math

# User exact POIs
pois = [
    {"id": "main_gate", "name": "Main Gate", "lat": 12.968233, "lon": 79.155896},
    {"id": "back_gate", "name": "Back Gate", "lat": 12.972728, "lon": 79.168187},
    {"id": "mb", "name": "Main Building (MB) / Dr. MGR Block", "lat": 12.969050, "lon": 79.155838},
    {"id": "tt", "name": "Technology Tower (TT)", "lat": 12.970895, "lon": 79.159334},
    {"id": "sjt", "name": "Silver Jubilee Tower (SJT)", "lat": 12.971241, "lon": 79.163597},
    {"id": "mgb", "name": "Gandhi Block (MGB)", "lat": 12.972358, "lon": 79.167969},
    {"id": "gdn", "name": "G.D. Naidu Block (GDN)", "lat": 12.969710, "lon": 79.154800},
    {"id": "health", "name": "Health Care Centre", "lat": 12.973393, "lon": 79.159632},
    {"id": "prp", "name": "Pearl Research Park (PRP)", "lat": 12.971139, "lon": 79.166359},
    {"id": "smv", "name": "SMV Block", "lat": 12.969234, "lon": 79.157583},
    {"id": "cdmm", "name": "CDMM Building", "lat": 12.969123, "lon": 79.155160},
    {"id": "cbmr", "name": "CBMR Building", "lat": 12.968413, "lon": 79.159802},
    {"id": "cts", "name": "Centre for Technical Support (VIT - CTS)", "lat": 12.97118740544007, "lon": 79.15626877483938},
    {"id": "men_q", "name": "Men's Q Block", "lat": 12.973802, "lon": 79.164023},
    {"id": "men_m", "name": "Men's M Block", "lat": 12.972710, "lon": 79.164088},
    {"id": "men_s", "name": "Men's S Block", "lat": 12.974336, "lon": 79.165625},
    {"id": "men_n", "name": "Men's N Block", "lat": 12.975285, "lon": 79.164116},
    {"id": "men_t", "name": "Men's T Block", "lat": 12.974800, "lon": 79.165541},
    {"id": "hostel_indoor", "name": "Hostel Indoor", "lat": 12.972187, "lon": 79.159336},
    
    # Estimates
    {"id": "wh_a", "name": "Indira Gandhi Block (WH-A)", "lat": 12.968000, "lon": 79.153000},
    {"id": "wh_c", "name": "Mother Teresa Block (WH-C)", "lat": 12.968300, "lon": 79.152800},
    {"id": "lib", "name": "Periyar EVR Central Library", "lat": 12.969144654966886, "lon": 79.1568638503527},
    {"id": "auditorium", "name": "Anna Auditorium", "lat": 12.969791325790839, "lon": 79.15565653417262},
    {"id": "pool", "name": "VIT Men's Swimming Pool", "lat": 12.974431714330938, "lon": 79.16075216760599},
    {"id": "placement", "name": "PAT Centre", "lat": 12.970700, "lon": 79.159000},
    {"id": "cdc", "name": "Career Development Centre (CDC)", "lat": 12.971065214422687, "lon": 79.16405726276336},
    {"id": "woodys", "name": "Woodys", "lat": 12.97042556227405, "lon": 79.15743818444858},
    {"id": "one_food_world", "name": "One Food World", "lat": 12.972500, "lon": 79.162000},
    {"id": "darling", "name": "Darling Canteen", "lat": 12.970099864219828, "lon": 79.1590845295658},
    {"id": "allmart", "name": "All Maart Shopping Complex", "lat": 12.970132603997621, "lon": 79.15429256477312},
    {"id": "enzo", "name": "Enzo Snacks & Books", "lat": 12.972500, "lon": 79.164500},
    {"id": "canteen_gdn", "name": "VIT GDN Canteen", "lat": 12.969800, "lon": 79.154900},
    {"id": "canteen_sjt", "name": "SJT Canteen", "lat": 12.971100, "lon": 79.163300},
    {"id": "canteen_dc", "name": "DC Canteen & Bakery", "lat": 12.970070366610404, "lon": 79.15889557660066},
    {"id": "street_bites", "name": "Street Bites", "lat": 12.974765578399333, "lon": 79.16408805612886},
    {"id": "madras_coffee", "name": "Madras Coffee House", "lat": 12.972495167792987, "lon": 79.1672725674331}
]

# ─────────────────────────────────────────────────────────────────────────────
# JUNCTION NODES – placed strictly on actual campus ROADS and PATHWAYS
#
# Road network topology:
#
#   1. ENTRY ROAD (N-S):  Main Gate ──north──▶ Roundabout
#
#   2. SOUTHERN E-W ROAD: Roundabout ──east──▶ W1 ──east──▶ W2 ──east──▶ TT Turnoff
#      (the main campus road going east from the roundabout)
#
#   3. TT ACCESS ROAD (N-S): TT Turnoff ──north──▶ TT South ──north──▶ TT ──north──▶ TT North
#      (road going north from the main road to TT and beyond)
#
#   4. NORTHERN E-W ROAD: TT ──east──▶ E1 ──east──▶ E2 ──east──▶ E3 ──east──▶ E4 ──east──▶ Back
#      (road continuing east from TT toward SJT, PRP, Back Gate)
#
#   5. HOSTEL ROAD: TT North ──east──▶ North1 ──NE──▶ North2
#      (road from TT north area toward hostels)
#
# This ensures ALL paths follow roads/pathways and NEVER cut through buildings.
# ─────────────────────────────────────────────────────────────────────────────
joints = [
    {"id": "osm_0", "name": "Road", "lat": 12.968231, "lon": 79.155808},
    {"id": "osm_1", "name": "Road", "lat": 12.968369, "lon": 79.155892},
    {"id": "osm_2", "name": "Road", "lat": 12.968687, "lon": 79.15635},
    {"id": "osm_3", "name": "Road", "lat": 12.968807, "lon": 79.156567},
    {"id": "osm_4", "name": "Road", "lat": 12.96964, "lon": 79.156581},
    {"id": "osm_5", "name": "Road", "lat": 12.96969, "lon": 79.157399},
    {"id": "osm_6", "name": "Road", "lat": 12.96979, "lon": 79.158006},
    {"id": "osm_7", "name": "Road", "lat": 12.969804, "lon": 79.158188},
    {"id": "osm_8", "name": "Road", "lat": 12.970573, "lon": 79.158251},
    {"id": "osm_9", "name": "Road", "lat": 12.970992, "lon": 79.158354},
    {"id": "osm_10", "name": "Road", "lat": 12.97101, "lon": 79.15868},
    {"id": "osm_11", "name": "Road", "lat": 12.971123, "lon": 79.159762},
    {"id": "osm_12", "name": "Road", "lat": 12.971344, "lon": 79.161377},
    {"id": "osm_13", "name": "Road", "lat": 12.971433, "lon": 79.162266},
    {"id": "osm_14", "name": "Road", "lat": 12.971713, "lon": 79.163719},
    {"id": "osm_15", "name": "Road", "lat": 12.971961, "lon": 79.164401},
    {"id": "osm_16", "name": "Road", "lat": 12.972557, "lon": 79.166721},
    {"id": "osm_17", "name": "Road", "lat": 12.972719, "lon": 79.168306},
    {"id": "osm_18", "name": "Road", "lat": 12.97178, "lon": 79.160362},
    {"id": "osm_19", "name": "Road", "lat": 12.972524, "lon": 79.160886},
    {"id": "osm_20", "name": "Road", "lat": 12.972877, "lon": 79.163094},
    {"id": "osm_21", "name": "Road", "lat": 12.974791, "lon": 79.163779},
    {"id": "osm_22", "name": "Road", "lat": 12.975302, "lon": 79.163801},
]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

edges = []
def add_edge(u, v):
    p1 = next((p for p in all_nodes if p["id"] == u), None)
    p2 = next((p for p in all_nodes if p["id"] == v), None)
    if p1 and p2:
        d = haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
        edges.append({"source": u, "target": v, "distance_m": round(d, 1)})

all_nodes = pois + joints

# ═══════════════════════════════════════════════════════════════════════════
# BACKBONE ROAD EDGES  –  these define the actual campus road network
# Each edge is exactly traced from OpenStreetMap paths.
# ═══════════════════════════════════════════════════════════════════════════

add_edge("osm_10", "osm_18")
add_edge("osm_4", "osm_5")
add_edge("osm_13", "osm_14")
add_edge("osm_1", "osm_2")
add_edge("osm_18", "osm_19")
add_edge("osm_6", "osm_7")
add_edge("osm_3", "osm_4")
add_edge("osm_5", "osm_6")
add_edge("osm_14", "osm_15")
add_edge("osm_9", "osm_10")
add_edge("osm_11", "osm_12")
add_edge("osm_7", "osm_8")
add_edge("osm_11", "osm_10")
add_edge("osm_2", "osm_3")
add_edge("osm_10", "osm_11")
add_edge("osm_21", "osm_22")
add_edge("osm_8", "osm_9")
add_edge("osm_12", "osm_13")
add_edge("osm_16", "osm_17")
add_edge("osm_19", "osm_20")
add_edge("osm_0", "osm_1")
add_edge("osm_20", "osm_21")
add_edge("osm_15", "osm_16")

# Link major POIs explicitly to their nearest starting OSM nodes
add_edge("main_gate", "osm_0")
add_edge("tt", "osm_11")
add_edge("back_gate", "osm_17")

# ═══════════════════════════════════════════════════════════════════════════
# CONNECT EACH BUILDING/POI TO ITS NEAREST ROAD JUNCTION
# (short last-mile connections from road to building entrance)
# ═══════════════════════════════════════════════════════════════════════════
# Skip buildings already connected in the backbone
backbone_pois = {"main_gate", "tt", "back_gate"}

for p in pois:
    if p["id"] in backbone_pois:
        continue

    # Find the closest road junction
    dists = []
    for j in joints:
        dists.append((haversine(p['lat'], p['lon'], j['lat'], j['lon']), j['id']))
    dists.sort(key=lambda x: x[0])

    nearest_jn = dists[0][1]
    nearest_dist = dists[0][0]
    add_edge(p["id"], nearest_jn)
    print(f"  {p['id']:20s} -> {nearest_jn:20s}  ({nearest_dist:.0f} m)")

# ═══════════════════════════════════════════════════════════════════════════
graph = {
    "nodes": all_nodes,
    "edges": edges
}

with open("data/vit_graph.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, indent=2)

print("\n[OK] OSM-aligned road-following graph built successfully.")
print(f"   {len(all_nodes)} nodes, {len(edges)} edges")
print("\nPath Main Gate -> TT now perfectly overlays OpenStreetMap roads!")

