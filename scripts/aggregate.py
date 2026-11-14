"""Aggregate saved agent traces and separately authored semantic reviews."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation import aggregate_agent, audit_template


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--traces', type=Path, required=True)
    p.add_argument('--reviews', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--template', action='store_true')
    args = p.parse_args()
    load = lambda path: json.loads(path.read_text(encoding='utf-8'))
    cases, traces = load(args.cases), load(args.traces)
    if args.template:
        result = audit_template(cases, traces)
    else:
        if not args.reviews:
            p.error('--reviews is required except with --template')
        result = aggregate_agent(cases, traces, load(args.reviews))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'written': str(args.output), 'template': args.template}))


if __name__ == '__main__':
    main()
