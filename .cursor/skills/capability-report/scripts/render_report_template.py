#!/usr/bin/env python3
"""Render a starter report template for Cloud Agent capability tests."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


def build_template() -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    return f"""# Cloud Agent Capability Report

Generated (UTC): {timestamp}

## Run Metadata

- Agent ID: TODO
- Scenario: TODO
- Repository: TODO
- Source ref: TODO
- Target branch: TODO

## Delegation Evidence

- Subagent marker(s):
  - TODO

## Skill Evidence

- Skill marker(s):
  - TODO

## Result

- Status: TODO (PASS | FAIL | PARTIAL)
- Notes:
  - TODO
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a markdown template for capability reports.",
    )
    parser.add_argument(
        "--output",
        default="reports/cloud-agent-capability-report.md",
        help="Where to write the report template.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.force:
        print(
            f"Refusing to overwrite existing file: {output_path}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    output_path.write_text(build_template(), encoding="utf-8")
    print(f"Wrote template to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
