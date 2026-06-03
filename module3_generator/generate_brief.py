import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from docx import Document
from module3_generator.mapping_rules import summarize_graph


def load_graph(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_nodes(nodes):
    if not nodes:
        return '—'
    return '\n'.join(f'- {node["text"]} (conf: {node.get("confidence", 0):.2f})' for node in nodes)


def build_text(graph):
    doc_id = graph.get('doc_id', 'unknown')
    source_file = graph.get('source_file', 'unknown')
    summary = summarize_graph(graph)

    main_claim = summary['main_claim']
    conclusion = summary['conclusion']
    evidence = summary['evidence']
    premises = summary['premises']
    rebuttals = summary['rebuttals']

    lines = [
        'АНАЛИТИЧЕСКАЯ СПРАВКА ПО ДЕЛУ',
        f'Документ: {doc_id}',
        f'Дата: {date.today().isoformat()}',
        f'Источник: {source_file}',
        '',
        '1. ПОЗИЦИЯ СТОРОНЫ / ОСНОВНОЙ ТЕЗИС',
        f'{main_claim["text"] if main_claim else "Не удалось определить основную позицию."}',
        f'(Уверенность модели: {main_claim.get("confidence", 0) * 100:.1f}%)' if main_claim else '',
        '',
        '2. ОБОСНОВАНИЕ ПОЗИЦИИ',
        '2.1 Правовые основания и нормы:',
        format_nodes(evidence),
        '2.2 Логические доводы:',
        format_nodes(premises),
        '',
        '3. ВОЗРАЖЕНИЯ ПРОТИВОПОЛОЖНОЙ СТОРОНЫ',
        format_nodes(rebuttals) if rebuttals else 'В проанализированном тексте возражения не выявлены.',
        '',
        '4. ВЫВОД',
        f'{conclusion["text"] if conclusion else "Не удалось сформировать вывод."}',
        f'(Уверенность модели: {conclusion.get("confidence", 0) * 100:.1f}%)' if conclusion else '',
        '',
        'Сформировано автоматически. Требует верификации юриста.',
    ]
    return '\n'.join(line for line in lines if line is not None)


def save_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def save_docx(path, text):
    doc = Document()
    for line in text.split('\n'):
        doc.add_paragraph(line)
    doc.save(path)


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a legal brief from a graph.')
    parser.add_argument('--graph', '-g', required=True, help='Input graph JSON file.')
    parser.add_argument('--output', '-o', required=True, help='Output file path (.txt or .docx).')
    parser.add_argument('--template', '-t', required=False, help='Optional template file (.txt) rendered with Jinja2. Variables: summary, graph.')
    return parser.parse_args()


def main():
    args = parse_args()
    graph = load_graph(Path(args.graph))
    # If template provided and is a text template, render with jinja2
    text = build_text(graph)
    if getattr(args, 'template', None):
        tpl_path = Path(args.template)
        if tpl_path.exists() and tpl_path.suffix.lower() == '.txt':
            try:
                from jinja2 import Template
                summary = summarize_graph(graph)
                tpl_text = tpl_path.read_text(encoding='utf-8')
                text = Template(tpl_text).render(summary=summary, graph=graph)
            except Exception:
                # fallback to default built text on any template/render error
                pass
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == '.docx':
        save_docx(output, text)
    else:
        save_text(output, text)
    print(f'Output generated: {output}')


if __name__ == '__main__':
    main()
