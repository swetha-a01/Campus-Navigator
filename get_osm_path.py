import json
import requests
import math
import heapq

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

query = """
[out:json];
(
  way["highway"](12.965,79.150,12.976,79.168);
);
out body;
>;
out skel qt;
"""

res = requests.post("http://overpass-api.de/api/interpreter", data={"data": query}).json()
nodes = {el["id"]: (el["lat"], el["lon"]) for el in res["elements"] if el["type"] == "node"}
ways = [el for el in res["elements"] if el["type"] == "way"]

adj = {}
for w in ways:
    if "nodes" not in w: continue
    wnodes = w["nodes"]
    for i in range(len(wnodes)-1):
        n1, n2 = wnodes[i], wnodes[i+1]
        c1, c2 = nodes.get(n1), nodes.get(n2)
        if not c1 or not c2: continue
        d = haversine(c1[0], c1[1], c2[0], c2[1])
        adj.setdefault(n1, []).append((d, n2))
        adj.setdefault(n2, []).append((d, n1))

def nearest_node(lat, lon):
    min_d, best = float('inf'), None
    for nid, (nlat, nlon) in nodes.items():
        if nid not in adj: continue
        d = haversine(lat, lon, nlat, nlon)
        if d < min_d: min_d, best = d, nid
    return best

def find_path(start_coords, end_coords):
    s = nearest_node(*start_coords)
    e = nearest_node(*end_coords)
    q = [(0, s, [])]
    visited = set()
    while q:
        cost, u, path = heapq.heappop(q)
        if u in visited: continue
        visited.add(u)
        path = path + [u]
        if u == e:
            return path
        for d, v in adj.get(u, []):
            if v not in visited:
                heapq.heappush(q, (cost + d, v, path))
    return []

# Points
mg = (12.968233, 79.155896)
tt = (12.970895, 79.159334)
backgate = (12.972728, 79.168187)
hostels = (12.975285, 79.164116) # Men's N block

paths = [
    ("Main_to_TT", find_path(mg, tt)),
    ("TT_to_BackGate", find_path(tt, backgate)),
    ("TT_to_Hostels", find_path(tt, hostels))
]

seen_coords = {}
joints_out = []
edges_out = []
j_count = 0

for name, path in paths:
    for i, n in enumerate(path):
        if i % 3 != 0 and i != len(path)-1: continue
        c = nodes[n]
        c = (round(c[0],6), round(c[1],6))
        
        # Don't duplicate nearby nodes
        found = False
        for sc_key, sc_id in seen_coords.items():
            if haversine(c[0], c[1], sc_key[0], sc_key[1]) < 10:
                c_id = sc_id
                found = True
                break
        
        if not found:
            c_id = f"osm_{j_count}"
            j_count += 1
            seen_coords[c] = c_id
            joints_out.append(f'    {{"id": "{c_id}", "name": "Road", "lat": {c[0]}, "lon": {c[1]}}},')
            
        if i > 0: # connect to previous preserved node in this path
            prev = None
            for pj in range(i-1, -1, -1):
                if pj % 3 == 0 or pj == len(path)-1 or pj == 0:
                    pc = (round(nodes[path[pj]][0],6), round(nodes[path[pj]][1],6))
                    for sc_key, sc_id in seen_coords.items():
                         if haversine(pc[0], pc[1], sc_key[0], sc_key[1]) < 10:
                             prev = sc_id
                             break
                    if prev: break
            if prev and prev != c_id:
                edges_out.append(f'add_edge("{prev}", "{c_id}")')

print("\njoints = [")
print("\n".join(joints_out))
print("]\n\n# Add edges")
unique_edges = set(edges_out)
print("\n".join(unique_edges))
