import argparse
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
# ArgumentMining-main is a git submodule inside the project root
ARG_MINING_ROOT = ROOT / "ArgumentMining-main"
PREDICT_SCRIPT = ARG_MINING_ROOT / "model" / "predict.py"
CONVERT_SCRIPT = ROOT / "convert_jsonl_to_graph.py"
RELATION_SCRIPT = ROOT / "module2_relations" / "build_relations_llm.py"
BRIEF_SCRIPT = ROOT / "module3_generator" / "generate_brief.py"


def run_cmd(cmd, cwd=None):
    print(f"Running: {' '.join(str(x) for x in cmd)}")
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def collect_jsonl_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.jsonl"))
    if path.suffix.lower() == ".jsonl":
        return [path]
    raise SystemExit(f"Annotated path must be a .jsonl file or directory: {path}")


def safe_name(name: str) -> str:
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in name).strip('_') or 'doc'


def run_annotation(input_path: Path, checkpoint: Path, temp_dir: Path) -> list[Path]:
    if not PREDICT_SCRIPT.exists():
        raise SystemExit(f"ArgumentMining-main predict script not found: {PREDICT_SCRIPT}")
    outputs = []
    # support passing a directory of raw files
    if input_path.is_dir():
        files = sorted([p for p in input_path.iterdir() if p.suffix.lower() in {'.txt', '.jsonl'}])
        if not files:
            raise SystemExit(f'No input files in directory: {input_path}')
        for f in files:
            out = temp_dir / f"{safe_name(f.stem)}_annotated.jsonl"
            cmd = [sys.executable, str(PREDICT_SCRIPT), "--input", str(f), "--output", str(out)]
            if checkpoint:
                cmd += ["--checkpoint", str(checkpoint)]
            run_cmd(cmd, cwd=ARG_MINING_ROOT)
            if not out.exists():
                raise SystemExit(f"Annotation output not found for {f}: expected {out}")
            outputs.append(out)
        return outputs

    if input_path.suffix.lower() == ".jsonl":
        output_path = temp_dir / "annotated"
    else:
        output_path = temp_dir / f"{safe_name(input_path.stem)}_annotated.jsonl"

    cmd = [sys.executable, str(PREDICT_SCRIPT), "--input", str(input_path), "--output", str(output_path)]
    if checkpoint:
        cmd += ["--checkpoint", str(checkpoint)]
    run_cmd(cmd, cwd=ARG_MINING_ROOT)

    if output_path.is_dir():
        files = sorted(output_path.glob("*.jsonl"))
        if not files:
            raise SystemExit(f"No annotated files were created in {output_path}")
        return files
    if output_path.exists():
        return [output_path]
    raise SystemExit(f"Annotation output not found: {output_path}")


def build_graphs(annotated_files: list[Path], temp_dir: Path) -> list[Path]:
    graph_dir = temp_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for annotated in annotated_files:
        graph_name = safe_name(annotated.stem) + "_nodes.json"
        graph_path = graph_dir / graph_name
        run_cmd([sys.executable, str(ROOT / "convert_jsonl_to_graph.py"), "--input", str(annotated), "--output", str(graph_path)])
        results.append(graph_path)
    return results


def build_relations(graph_files: list[Path], window: int, temp_dir: Path) -> list[Path]:
    results = []
    for graph in graph_files:
        out_path = graph.with_name(graph.stem + "_graph.json")
        cmd = [sys.executable, str(RELATION_SCRIPT), "--input", str(graph), "--output", str(out_path), "--window", str(window)]
        # pass provider/model if set via env args
        if getattr(build_relations, 'provider', None):
            cmd += ["--provider", build_relations.provider]
        if getattr(build_relations, 'model', None):
            cmd += ["--model", build_relations.model]
        run_cmd(cmd)
        results.append(out_path)
    return results


def generate_briefs(graph_files: list[Path], output: Path, fmt: str) -> list[Path]:
    output_paths = []
    if output.suffix.lower() in {".txt", ".docx"}:
        if len(graph_files) != 1:
            raise SystemExit("Если указан файл, можно обработать только один граф.")
        output_paths = [output]
    else:
        output.mkdir(parents=True, exist_ok=True)
        for graph in graph_files:
            doc_name = graph.stem.replace("_graph", "")
            output_paths.append(output / f"{doc_name}.{fmt}")

    for graph, out_path in zip(graph_files, output_paths):
        cmd = [sys.executable, str(BRIEF_SCRIPT), "--graph", str(graph), "--output", str(out_path)]
        if getattr(generate_briefs, 'template', None):
            cmd += ["--template", generate_briefs.template]
        run_cmd(cmd)
    return output_paths


def parse_args():
    parser = argparse.ArgumentParser(description="Run the full legal brief pipeline from annotation to final text.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Raw input file (.txt or .jsonl) to annotate with ArgumentMining-main.")
    group.add_argument("--annotated", help="Annotated JSONL file or directory with annotations.")
    parser.add_argument("--output", required=True, help="Output file or directory for generated briefs.")
    parser.add_argument("--checkpoint", default=None, help="Optional path to ruBERT checkpoint for ArgumentMining-main.")
    parser.add_argument("--window", type=int, default=5, help="Max sentence window for relation extraction.")
    parser.add_argument("--format", choices=["txt", "docx"], default="txt", help="Output brief format.")
    # default to local ollama + gguf file in project root when available
    default_model = None
    default_model_path = ROOT / 'gemma-4-E4B-it-Q4_K_M.gguf'
    if default_model_path.exists():
        default_model = str(default_model_path)
    parser.add_argument('--provider', choices=['heuristic', 'gemini', 'ollama'], default='ollama', help='LLM provider for relation extraction.')
    parser.add_argument('--model', default=default_model, help='Optional model name for the provider. If a gguf file gemma-4-E4B-it-Q4_K_M.gguf exists in project root it will be used by default.')
    parser.add_argument('--template', default=None, help='Optional text template for briefs (.txt).')
    return parser.parse_args()


def main():
    args = parse_args()
    output_path = Path(args.output)
    annotated_dir = None
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        if args.annotated:
            annotated_dir = Path(args.annotated)
            annotated_files = collect_jsonl_files(annotated_dir)
        else:
            input_path = Path(args.input)
            checkpoint = Path(args.checkpoint) if args.checkpoint else None
            annotated_files = run_annotation(input_path, checkpoint, temp_dir)

        graph_nodes = build_graphs(annotated_files, temp_dir)
        # attach provider/model to function objects so inner build_relations can access
        build_relations.provider = args.provider
        build_relations.model = args.model
        generate_briefs.template = args.template
        graph_with_relations = build_relations(graph_nodes, args.window, temp_dir)
        output_files = generate_briefs(graph_with_relations, output_path, args.format)

        print("\nPipeline completed. Generated briefs:")
        for out_file in output_files:
            print(f"  - {out_file}")


if __name__ == "__main__":
    main()
