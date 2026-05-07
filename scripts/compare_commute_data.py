#!/usr/bin/env python3
"""Compare generated commute data JSON files after canonical normalization."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def load(path: Path) -> str:
    try:
        return json.dumps(
            canonicalize(json.loads(path.read_text(encoding="utf-8"))),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except FileNotFoundError:
        print(f"missing file: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as error:
        print(f"invalid JSON in {path}: {error}", file=sys.stderr)
        raise SystemExit(2)


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: compare_commute_data.py BASELINE CURRENT", file=sys.stderr)
        raise SystemExit(2)

    baseline_path = Path(sys.argv[1])
    current_path = Path(sys.argv[2])
    if load(baseline_path) != load(current_path):
        print(f"commute data differs: {baseline_path} != {current_path}", file=sys.stderr)
        raise SystemExit(1)

    print(f"commute data matches: {current_path}")


if __name__ == "__main__":
    main()
