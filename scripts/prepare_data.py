"""Rebuild the Day07 index independently from the pinned permitted Day06 snapshot."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval import ROOT, prepare_day6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6-root", type=Path, help="Optional local Day06 checkout; absent means download files at pinned Git commit")
    parser.add_argument("--root", type=Path, default=ROOT, help="Day07 output root; allows isolated reproduction")
    args = parser.parse_args()
    manifest = prepare_day6(args.day6_root, args.root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
