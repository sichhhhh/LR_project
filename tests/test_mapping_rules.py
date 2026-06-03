from module3_generator.mapping_rules import summarize_graph


def test_summarize_graph():
    graph = {
        'nodes': [
            {'id': 'n0', 'text': 'Основной тезис.', 'label': 'CLAIM', 'confidence': 0.9, 'position': 0},
            {'id': 'n1', 'text': 'Доказательство.', 'label': 'EVIDENCE', 'confidence': 0.8, 'position': 1},
            {'id': 'n2', 'text': 'Возражение.', 'label': 'REBUTTAL', 'confidence': 0.7, 'position': 2},
        ],
        'edges': [
            {'source': 'n1', 'target': 'n0', 'relation': 'support', 'confidence': 0.8},
            {'source': 'n2', 'target': 'n0', 'relation': 'attack', 'confidence': 0.7},
        ]
    }
    result = summarize_graph(graph)
    assert result['main_claim']['id'] == 'n0'
    assert result['conclusion']['id'] == 'n0'
    assert len(result['evidence']) == 1
    assert len(result['rebuttals']) == 1
