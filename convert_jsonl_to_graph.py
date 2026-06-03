import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def load_jsonl(path):
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _safe_filename(name: str) -> str:
    name = re.sub(r'[^\\x00-\\x7f]+', '_', name)
    name = re.sub(r'[^0-9A-Za-z_.-]+', '_', name)
    return name.strip('_') or 'doc'


def group_by_doc(rows):
    docs = defaultdict(list)
    for row in rows:
        doc_id = str(row.get('doc_id') or row.get('source_file') or 'unknown')
        docs[doc_id].append(row)
    return docs


def build_graph(nodes, doc_id=None, source_file=None):
    graph = {
        'doc_id': doc_id or nodes[0].get('doc_id', 'unknown'),
        'source_file': source_file or nodes[0].get('source_file', ''),
        'metadata': nodes[0].get('metadata', {}),
        'nodes': [],
        'edges': [],
    }

    for idx, item in enumerate(nodes):
        node_id = item.get('id') or f'n{idx}'
        graph['nodes'].append({
            'id': node_id,
            'text': item.get('text', '').strip(),
            'label': item.get('label', 'NON_ARG'),
            'confidence': float(item.get('confidence', 0.0)),
            'position': int(item.get('position', idx)),
        })

    return graph


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(description='Convert Module I JSONL to graph JSON.')
    parser.add_argument('--input', '-i', required=True, help='Input JSONL file with annotated sentences.')
    parser.add_argument('--output', '-o', required=True, help='Output graph JSON file or directory.')
    parser.add_argument('--source-file', help='Optional source filename for metadata.')
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    rows = list(load_jsonl(input_path))
    if not rows:
        raise SystemExit('Input file is empty or invalid JSONL.')

    grouped = group_by_doc(rows)
    if len(grouped) == 1:
        doc_id, items = next(iter(grouped.items()))
        graph = build_graph(items, doc_id=doc_id, source_file=args.source_file)
        if output_path.suffix.lower() in {'.json', '.jsonl'}:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            save_json(output_path, graph)
            print(f'Graph saved: {output_path}')
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            graph_file = output_path / f'{_safe_filename(doc_id)}_graph.json'
            save_json(graph_file, graph)
            print(f'Graph saved: {graph_file}')
    else:
        if output_path.suffix.lower() in {'.json', '.jsonl'}:
            raise SystemExit('Output must be a directory when input contains multiple documents.')
        output_path.mkdir(parents=True, exist_ok=True)
        for doc_id, items in grouped.items():
            graph = build_graph(items, doc_id=doc_id, source_file=args.source_file)
            graph_file = output_path / f'{_safe_filename(doc_id)}_graph.json'
            save_json(graph_file, graph)
            print(f'Graph saved: {graph_file}')


if __name__ == '__main__':
    main()
