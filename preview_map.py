import json
import folium

with open('data/vit_graph.json', 'r') as f:
    graph = json.load(f)

# Center roughly
m = folium.Map(location=[12.97, 79.16], zoom_start=16, tiles='CartoDB Positron')

node_map = {}
for n in graph['nodes']:
    node_map[n['id']] = (n['lat'], n['lon'])
    c = 'red' if n['id'].startswith('jn_') else 'blue'
    text = n.get('name', n['id'])
    folium.CircleMarker(
        location=(n['lat'], n['lon']),
        radius=5,
        popup=f"{text} ({n['id']})",
        tooltip=text,
        color=c,
        fill=True,
        fill_color=c
    ).add_to(m)

for e in graph['edges']:
    n1, n2 = e['source'], e['target']
    if n1 in node_map and n2 in node_map:
        folium.PolyLine(
            locations=[node_map[n1], node_map[n2]],
            color='green',
            weight=3
        ).add_to(m)

m.add_child(folium.LatLngPopup())
m.save('preview_map.html')
print("Map saved to preview_map.html")
