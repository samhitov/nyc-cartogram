#!/usr/bin/env python3
"""Check that frontend travel classification uses generated land masks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "site" / "app.js"


def main() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    required_snippets = (
        "function pointInLandMask(point)",
        "if (pointInLandMask(point)) return \"land\";",
    )
    missing = [snippet for snippet in required_snippets if snippet not in source]
    if missing:
        raise SystemExit(f"site/app.js does not classify generated landMask as land: missing {missing[0]}")


if __name__ == "__main__":
    main()
