"""Offline configuration check; --probe makes one explicitly requested API call."""
import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model_client import ModelClient, ModelError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Make one real model call (may incur cost)")
    args = parser.parse_args()
    result = {"python": platform.python_version(), "packages": {}, "api_probe": "not_requested"}
    for package in ("fastembed", "qdrant-client", "numpy"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = None
    try:
        model = ModelClient.from_env(root=ROOT)
        result["model"] = model.public_config()
        result["key_present"] = True
        if args.probe:
            response = model.complete([{"role": "user", "content": 'Return only {"connection":"ok"}.'}])
            result["api_probe"] = {k: response[k] for k in ("text", "model", "usage", "request_id", "latency_ms", "attempts")}
    except (ValueError, ModelError) as exc:
        result["error"] = str(exc)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
