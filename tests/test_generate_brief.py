from module3_generator.generate_brief import build_text


def test_build_text():
    graph = {
        'doc_id': 'doc_001',
        'source_file': 'input.jsonl',
        'nodes': [
            {'id': 'n0', 'text': 'Истец просит признать договор недействительным.', 'label': 'CLAIM', 'confidence': 0.92, 'position': 0},
            {'id': 'n1', 'text': 'Согласно ст. 168 ГК РФ, сделка ничтожна.', 'label': 'EVIDENCE', 'confidence': 0.87, 'position': 1},
        ],
        'edges': [
            {'source': 'n1', 'target': 'n0', 'relation': 'support', 'confidence': 0.8}
        ]
    }
    text = build_text(graph)
    assert 'ПОЗИЦИЯ' in text
    assert 'Истец просит признать договор недействительным.' in text
    assert 'Согласно ст. 168 ГК РФ' in text
