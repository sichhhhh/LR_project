from typing import Dict, List, Optional

LABEL_GROUPS = {
    'claim': {'CLAIM'},
    'premise': {'PREMISE'},
    'evidence': {'EVIDENCE'},
    'rebuttal': {'REBUTTAL'},
}


def get_node_by_id(nodes, node_id):
    return next((node for node in nodes if node['id'] == node_id), None)


def select_position(nodes, edges):
    candidates = [n for n in nodes if n['label'] == 'CLAIM']
    if not candidates:
        return None
    score = []
    for node in candidates:
        support_out = sum(1 for e in edges if e['source'] == node['id'] and e['relation'] == 'support')
        score.append((support_out, -node['position'], node))
    return max(score)[2]


def select_conclusion(nodes, edges):
    candidates = [n for n in nodes if n['label'] == 'CLAIM']
    if not candidates:
        return None
    score = []
    for node in candidates:
        support_in = sum(1 for e in edges if e['target'] == node['id'] and e['relation'] == 'support')
        score.append((support_in, node['position'], node))
    return max(score)[2]


def collect_supporting(nodes, edges, root_id):
    supporting = []
    if root_id is None:
        return supporting
    visited = set()
    reverse_graph = {n['id']: [] for n in nodes}
    for edge in edges:
        if edge['relation'] == 'support':
            reverse_graph[edge['target']].append(edge['source'])
    stack = [root_id]
    while stack:
        current = stack.pop()
        for parent in reverse_graph.get(current, []):
            if parent not in visited:
                visited.add(parent)
                stack.append(parent)
                node = get_node_by_id(nodes, parent)
                if node and node['label'] in LABEL_GROUPS['premise'].union(LABEL_GROUPS['evidence']):
                    supporting.append(node)
    return supporting


def collect_rebuttals(nodes, edges, root_id):
    if root_id is None:
        return []
    rebuttals = []
    for edge in edges:
        if edge['relation'] == 'attack' and edge['target'] == root_id:
            node = get_node_by_id(nodes, edge['source'])
            if node:
                rebuttals.append(node)
    return rebuttals


def summarize_graph(graph):
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    main_claim = select_position(nodes, edges)
    conclusion = select_conclusion(nodes, edges)
    evidence = collect_supporting(nodes, edges, main_claim['id'] if main_claim else None)
    rebuttals = collect_rebuttals(nodes, edges, main_claim['id'] if main_claim else None)

    return {
        'main_claim': main_claim,
        'evidence': [n for n in evidence if n['label'] == 'EVIDENCE'],
        'premises': [n for n in evidence if n['label'] == 'PREMISE'],
        'rebuttals': rebuttals,
        'conclusion': conclusion,
    }
