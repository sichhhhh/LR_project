import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from convert_jsonl_to_graph import build_graph, load_jsonl, save_json
from module2_relations.build_relations_llm import build_relations
from module3_generator.generate_brief import build_text


if __name__ == '__main__':
    base = Path(__file__).resolve().parent.parent
    example_jsonl = base / 'data' / 'examples' / 'example_input.jsonl'
    nodes_path = base / 'data' / 'examples' / 'example_graph.json'
    graph_path = base / 'output' / 'example_graph.json'
    brief_path = base / 'output' / 'brief_example.txt'

    if not example_jsonl.exists():
        raise SystemExit(f'Missing example input: {example_jsonl}')

    nodes = list(load_jsonl(example_jsonl))
    graph = build_graph(nodes, source_file='example_input.jsonl')
    graph['edges'] = build_relations(graph, window=5)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(graph_path, graph)

    text = build_text(graph)
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(text, encoding='utf-8')
    print(f'Demo completed. Generated: {brief_path}')
