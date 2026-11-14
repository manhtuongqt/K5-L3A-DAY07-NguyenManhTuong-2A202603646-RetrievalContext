"""Run evaluator-only original-question top-3 retrieval comparison."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation import evaluate_retrieval


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--split', choices=('dev', 'test'), required=True)
    p.add_argument('--method', choices=('dense', 'bm25', 'hybrid'), required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.split == 'test' and not (ROOT / 'results/selection.json').exists():
        p.error('Freeze results/selection.json before evaluating test.')
    from src.retrieval import RetrievalService
    cases = json.loads((ROOT / f'benchmark/{args.split}.json').read_text(encoding='utf-8'))
    service = RetrievalService(root=ROOT)
    try:
        traces, summary = evaluate_retrieval(service, cases, args.method)
    finally:
        if hasattr(service, 'close'):
            service.close()
    out = args.output or ROOT / 'results/retrieval' / args.split / args.method
    out.mkdir(parents=True, exist_ok=True)
    for name, value in [('traces.json', traces), ('summary.json', summary)]:
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
