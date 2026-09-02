"""``oadiff`` command-line entry point."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .change import Severity
from .diff import diff_specs
from .loader import SpecLoadError, load_spec
from .normalize import normalize
from .report import RENDERERS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oadiff",
        description=(
            "Diff two OpenAPI/Swagger specs (JSON or YAML) and classify each "
            "change as breaking or non-breaking for API consumers."
        ),
    )
    parser.add_argument("old_spec", help="path to the old/base spec (JSON or YAML)")
    parser.add_argument("new_spec", help="path to the new/candidate spec (JSON or YAML)")
    parser.add_argument(
        "--format", "-f", choices=sorted(RENDERERS), default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="write the report to FILE instead of stdout",
    )
    parser.add_argument(
        "--fail-on-breaking", action="store_true",
        help="exit with status 1 if any breaking change is found (for CI gates)",
    )
    parser.add_argument(
        "--only-breaking", action="store_true",
        help="only include breaking changes (and changes needing review) in the report",
    )
    parser.add_argument("--version", action="version", version=f"oadiff {__version__}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        old_raw = load_spec(args.old_spec)
        new_raw = load_spec(args.new_spec)
    except (SpecLoadError, OSError) as exc:
        print(f"oadiff: error: {exc}", file=sys.stderr)
        return 2

    try:
        old_norm = normalize(old_raw)
        new_norm = normalize(new_raw)
    except ValueError as exc:
        print(f"oadiff: error: could not read spec structure: {exc}", file=sys.stderr)
        return 2

    changes = diff_specs(old_norm, new_norm)
    if args.only_breaking:
        changes = [c for c in changes if c.severity in (Severity.BREAKING, Severity.UNKNOWN)]

    renderer = RENDERERS[args.format]
    report = renderer(changes, args.old_spec, args.new_spec)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        sys.stdout.write(report)

    if args.fail_on_breaking and any(c.severity == Severity.BREAKING for c in changes):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
