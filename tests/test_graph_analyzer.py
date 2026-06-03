import json
from module3_generator.graph_analyzer import build_digraph, compute_degrees


def test_compute_degrees():
    graph = {
        'nodes': [
            {'id': 'n0', 'text': 'A', 'label': 'CLAIM', 'confidence': 0.9, 'position': 0},
            {'id': 'n1', 'text': 'B', 'label': 'EVIDENCE', 'confidence': 0.8, 'position': 1},
        ],
        'edges': [
            {'source': 'n1', 'target': 'n0', 'relation': 'support', 'confidence': 0.8}
        ]
    }
    degrees = compute_degrees(graph)
    assert degrees['n0']['support_in'] == 1
    assert degrees['n1']['support_out'] == 1
