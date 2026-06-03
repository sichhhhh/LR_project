import argparse
import json
import os
import re
import time
from pathlib import Path

LABEL_SUPPORTERS = {'EVIDENCE', 'PREMISE'}
LABEL_ATTACKERS = {'REBUTTAL'}


def load_graph(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def should_support(label_a, label_b, text_a, text_b):
    if label_a in LABEL_SUPPORTERS and label_b == 'CLAIM':
        return True
    if label_a == 'PREMISE' and label_b in {'CLAIM', 'EVIDENCE', 'PREMISE'}:
        return True
    if label_a == 'EVIDENCE' and label_b in {'CLAIM', 'PREMISE'}:
        return True
    return False


def should_attack(label_a, label_b, text_a, text_b):
    if label_a in LABEL_ATTACKERS and label_b in {'CLAIM', 'PREMISE', 'EVIDENCE'}:
        return True
    if label_a == 'CLAIM' and label_b == 'CLAIM':
        # heuristic: competing claims within a short window are likely attack/neutral
        return bool(re.search(r'не|не является|оспаривает|оспаривается|не подтверждает|отрица', text_a, re.IGNORECASE))
    return False


def build_relations(graph, window):
    nodes = sorted(graph['nodes'], key=lambda x: x['position'])
    candidates = [n for n in nodes if n['label'] != 'NON_ARG']
    edges = []

    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if abs(a['position'] - b['position']) > window:
                continue
            # default heuristic
            relation = 'neutral'
            confidence = 0.5
            if should_support(a['label'], b['label'], a['text'], b['text']):
                relation = 'support'
                confidence = 0.8
            elif should_attack(a['label'], b['label'], a['text'], b['text']):
                relation = 'attack'
                confidence = 0.8
            elif should_attack(b['label'], a['label'], b['text'], a['text']):
                relation = 'attack'
                confidence = 0.8
                a, b = b, a
            edges.append({
                'source': a['id'],
                'target': b['id'],
                'relation': relation,
                'confidence': confidence,
            })
    return edges


def call_gemini_for_pair(a, b, model='gemini'):
    try:
        import google.generativeai as genai
    except Exception:
        return None
    api_key = os.environ.get('GOOGLE_AI_API_KEY')
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    prompt = (
        "Ты — юридический аналитик. Определи тип связи между двумя фрагментами правового текста.\n"
        "Типы связей: support, attack, neutral.\n"
        f"A [{a['label']}]: \"{a['text']}\"\n"
        f"B [{b['label']}]: \"{b['text']}\"\n"
        "Ответ форматом: support|attack|neutral"
    )
    try:
        resp = genai.generate_text(model=model, prompt=prompt)
        text = getattr(resp, 'text', '') or str(resp)
        text = text.strip().lower()
        if 'support' in text:
            return 'support', 0.85
        if 'attack' in text:
            return 'attack', 0.85
        return 'neutral', 0.5
    except Exception:
        return None


def call_ollama_for_pair(a, b, host=None, model=None):
    try:
        import requests
    except Exception:
        return None
    host = host or os.environ.get('OLLAMA_HOST')
    model = model or os.environ.get('OLLAMA_MODEL')
    # Allow using a local gguf model file placed in the project root as default
    if not model:
        default_model_path = Path(__file__).resolve().parents[1] / 'gemma-4-E4B-it-Q4_K_M.gguf'
        if default_model_path.exists():
            model = str(default_model_path)
    if not host and not model:
        return None
    prompt = (
        "Ты — юридический аналитик. Определи тип связи между двумя фрагментами правового текста.\n"
        "Типы связей: support, attack, neutral.\n"
        f"A [{a['label']}]: \"{a['text']}\"\n"
        f"B [{b['label']}]: \"{b['text']}\"\n"
        "Ответ форматом: support|attack|neutral"
    )
    try:
        # If host is provided, prefer HTTP API
        if host:
            url = host.rstrip('/') + '/api/generate'
            payload = {"model": model, "prompt": prompt, "max_tokens": 64}
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                text = r.text.lower()
                if 'support' in text:
                    return 'support', 0.85
                if 'attack' in text:
                    return 'attack', 0.85
                return 'neutral', 0.5
            return None

        # Fallback: try local 'ollama' CLI if available and model is a path or registered name
        import subprocess
        cmd = ['ollama', 'run', str(model), '--prompt', prompt, '--no-stream']
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = (proc.stdout or proc.stderr).lower()
            if 'support' in out:
                return 'support', 0.85
            if 'attack' in out:
                return 'attack', 0.85
            return 'neutral', 0.5
        except FileNotFoundError:
            return None
    except Exception:
        return None


def build_relations_with_llm(graph, window, provider='heuristic', model=None):
    nodes = sorted(graph['nodes'], key=lambda x: x['position'])
    candidates = [n for n in nodes if n['label'] != 'NON_ARG']
    edges = []
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if abs(a['position'] - b['position']) > window:
                continue
            # try LLM provider first
            relation = None
            confidence = 0.5
            if provider == 'gemini':
                res = call_gemini_for_pair(a, b, model=model or 'gemini')
                if res:
                    relation, confidence = res
            elif provider == 'ollama':
                res = call_ollama_for_pair(a, b, host=os.environ.get('OLLAMA_HOST'), model=model or os.environ.get('OLLAMA_MODEL'))
                if res:
                    relation, confidence = res

            # fallback to heuristic when LLM not available or returned None
            if not relation:
                if should_support(a['label'], b['label'], a['text'], b['text']):
                    relation = 'support'
                    confidence = 0.8
                elif should_attack(a['label'], b['label'], a['text'], b['text']):
                    relation = 'attack'
                    confidence = 0.8
                elif should_attack(b['label'], a['label'], b['text'], a['text']):
                    relation = 'attack'
                    confidence = 0.8
                    a, b = b, a
                else:
                    relation = 'neutral'
                    confidence = 0.5

            edges.append({
                'source': a['id'],
                'target': b['id'],
                'relation': relation,
                'confidence': confidence,
            })
            # brief pause to respect rate limits when using remote providers
            if provider in ('gemini', 'ollama'):
                time.sleep(0.2)
    return edges


def save_graph(path, graph):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(description='Build relations graph from node-only graph JSON.')
    parser.add_argument('--input', '-i', required=True, help='Input graph JSON with nodes.')
    parser.add_argument('--output', '-o', required=True, help='Output graph JSON with edges.')
    parser.add_argument('--window', '-w', type=int, default=5, help='Maximum position window for candidate pairs.')
    # default to local ollama + the gguf model in project root when available
    default_model_path = Path(__file__).resolve().parents[1] / 'gemma-4-E4B-it-Q4_K_M.gguf'
    parser.add_argument('--provider', choices=['heuristic', 'gemini', 'ollama'], default='ollama', help='LLM provider to use for relation extraction. Heuristic fallback used when provider unavailable.')
    parser.add_argument('--model', default=str(default_model_path) if default_model_path.exists() else None, help='Optional model name or path for the chosen provider. If a gguf file named gemma-4-E4B-it-Q4_K_M.gguf exists in the project root it will be used by default.')
    return parser.parse_args()


def main():
    args = parse_args()
    graph = load_graph(Path(args.input))
    edges = build_relations_with_llm(graph, window=args.window, provider=args.provider, model=args.model)
    graph['edges'] = edges
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    save_graph(Path(args.output), graph)
    print(f'Relations built: {len(edges)} edges')


if __name__ == '__main__':
    main()
