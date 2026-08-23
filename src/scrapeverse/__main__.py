"""CLI entry point: `python -m scrapeverse` or `scrapeverse` console script."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .brightdata import BrightDataError
from .config import load_settings, load_targets
from .pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scrapeverse", description=__doc__)
    parser.add_argument("--target", help="Run a single target by name")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    settings = load_settings()
    targets = load_targets()
    if args.target:
        targets = [t for t in targets if t.name == args.target]
        if not targets:
            print(f"No target named {args.target!r}", file=sys.stderr)
            return 2

    try:
        reports = run_pipeline(settings, targets)
    except BrightDataError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([r.__dict__ for r in reports], indent=2, default=str))
    else:
        for r in reports:
            icon = {"ok": "✅", "healed": "🩹", "failed": "❌"}[r.status]
            print(f"{icon} {r.target}: {r.status}, {r.row_count} rows")
            for e in r.healing_events:
                print(f"   {e}")
            if r.error:
                print(f"   error: {r.error}")
    return 0 if all(r.status != "failed" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
