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

from ai_diabetology_llm.pipeline import ingest_completed_batches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest completed OpenAI Batch result files into the cache.")
    parser.add_argument(
        "--config",
        default="sidecars/llm_affiliation_classification/config/sidecar.yaml",
        help="Path to sidecar config YAML.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = ingest_completed_batches(args.config, project_root=args.project_root)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
