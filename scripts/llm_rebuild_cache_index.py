#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai_diabetology_llm.pipeline import rebuild_cache_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild parsed LLM cache indices from raw response files.")
    parser.add_argument(
        "--config",
        default="sidecars/llm_affiliation_classification/config/sidecar.yaml",
        help="Path to sidecar config YAML.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = rebuild_cache_index(args.config, project_root=args.project_root)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
