import networkx as nx


def build_digraph(graph):
    G = nx.DiGraph()
    for node in graph.get('nodes', []):
        G.add_node(node['id'], **node)
    for edge in graph.get('edges', []):
        G.add_edge(edge['source'], edge['target'], **edge)
    return G


def compute_degrees(graph):
    G = build_digraph(graph)
    degrees = {}
    for node_id in G.nodes:
        degrees[node_id] = {
            'in_degree': G.in_degree(node_id),
            'out_degree': G.out_degree(node_id),
            'support_in': sum(1 for _, _, d in G.in_edges(node_id, data=True) if d.get('relation') == 'support'),
            'support_out': sum(1 for _, _, d in G.out_edges(node_id, data=True) if d.get('relation') == 'support'),
            'attack_in': sum(1 for _, _, d in G.in_edges(node_id, data=True) if d.get('relation') == 'attack'),
            'attack_out': sum(1 for _, _, d in G.out_edges(node_id, data=True) if d.get('relation') == 'attack'),
        }
    return degrees


def connected_components(graph):
    G = build_digraph(graph)
    return [list(comp) for comp in nx.weakly_connected_components(G)]
