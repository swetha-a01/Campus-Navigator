import json
import math
import requests

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

print("Fetching road network from Overpass...")
overpass_url = "http://overpass-api.de/api/interpreter"
overpass_query = """
[out:json];
(
  way["highway"](12.965,79.150,12.976,79.165);
);
out body;
>;
out skel qt;
"""
response = requests.post(overpass_url, data={'data': overpass_query})
data = response.json()

node_coords = {}
for element in data['elements']:
    if element['type'] == 'node':
        node_coords[element['id']] = (element['lat'], element['lon'])

ways = []
for element in data['elements']:
    if element['type'] == 'way':
        if 'nodes' in element:
            way_nodes = [node_coords[n] for n in element['nodes'] if n in node_coords]
            ways.append(way_nodes)

print(f"Loaded {len(ways)} ways.")

import pathlib
graph_path = pathlib.Path("data/vit_graph.json")
with open(graph_path, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

def point_to_segment_dist(px, py, x1, y1, x2, y2):
    # px,py -> lat, lon
    # approximation since distances are very small
    l2 = (x2 - x1)**2 + (y2 - y1)**2
    if l2 == 0:
        return haversine(px, py, x1, y1), (x1, y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    return haversine(px, py, proj_x, proj_y), (proj_x, proj_y)

def find_closest_road_point(lat, lon):
    min_dist = float('inf')
    best_point = (lat, lon)
    for way in ways:
        for i in range(len(way)-1):
            n1 = way[i]
            n2 = way[i+1]
            dist, pt = point_to_segment_dist(lat, lon, n1[0], n1[1], n2[0], n2[1])
            if dist < min_dist:
                min_dist = dist
                best_point = pt
    return best_point, min_dist

for node in graph_data["nodes"]:
    old_lat, old_lon = node["lat"], node["lon"]
    best_pt, dist = find_closest_road_point(old_lat, old_lon)
    print(f"Moved {node['id']} by {dist:.1f}m")
    if dist < 100: # don't snap if it's too far (sanity check)
        node["lat"] = round(best_pt[0], 6)
        node["lon"] = round(best_pt[1], 6)

with open(graph_path, "w", encoding="utf-8") as f:
    json.dump(graph_data, f, indent=2)
print("Saved vit_graph_snapped.json")
