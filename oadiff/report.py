"""Render a list of :class:`~oadiff.change.Change` records as text, markdown,
or JSON."""

from __future__ import annotations

import json
from typing import List

from .change import Change, Severity

_SEVERITY_ORDER = {Severity.BREAKING: 0, Severity.UNKNOWN: 1, Severity.NON_BREAKING: 2}
_SEVERITY_LABEL = {
    Severity.BREAKING: "BREAKING",
    Severity.NON_BREAKING: "non-breaking",
    Severity.UNKNOWN: "needs review",
}


def _sort_key(c: Change):
    return (_SEVERITY_ORDER[c.severity], c.method, c.path, c.location)


def summarize(changes: List[Change]) -> dict:
    counts = {s.value: 0 for s in Severity}
    for c in changes:
        counts[c.severity.value] += 1
    counts["total"] = len(changes)
    return counts


def render_text(changes: List[Change], old_name: str = "old", new_name: str = "new") -> str:
    counts = summarize(changes)
    lines = [f"Comparing {old_name} -> {new_name}", ""]
    lines.append(
        f"{counts['breaking']} breaking, {counts['non-breaking']} non-breaking, "
        f"{counts['unknown']} needs review ({counts['total']} total changes)"
    )
    if not changes:
        lines.append("")
        lines.append("No differences found.")
        return "\n".join(lines) + "\n"

    lines.append("")
    for c in sorted(changes, key=_sort_key):
        label = _SEVERITY_LABEL[c.severity]
        where = f"{c.method} {c.path}".strip() or "(spec-level)"
        loc = f" [{c.location}]" if c.location else ""
        lines.append(f"[{label:12}] {where}{loc}: {c.message}")
    return "\n".join(lines) + "\n"


def render_markdown(changes: List[Change], old_name: str = "old", new_name: str = "new") -> str:
    counts = summarize(changes)
    lines = [f"# API diff: `{old_name}` -> `{new_name}`", ""]
    lines.append(
        f"**{counts['breaking']} breaking**, {counts['non-breaking']} non-breaking, "
        f"{counts['unknown']} needs review ({counts['total']} total changes)"
    )
    lines.append("")
    if not changes:
        lines.append("No differences found.")
        return "\n".join(lines) + "\n"

    for severity in (Severity.BREAKING, Severity.UNKNOWN, Severity.NON_BREAKING):
        subset = [c for c in changes if c.severity == severity]
        if not subset:
            continue
        lines.append(f"## {_SEVERITY_LABEL[severity]} ({len(subset)})")
        lines.append("")
        lines.append("| Endpoint | Location | Change |")
        lines.append("| --- | --- | --- |")
        for c in sorted(subset, key=_sort_key):
            where = f"{c.method} {c.path}".strip() or "(spec-level)"
            loc = c.location or "-"
            message = c.message.replace("|", "\\|")
            lines.append(f"| `{where}` | `{loc}` | {message} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(changes: List[Change], old_name: str = "old", new_name: str = "new") -> str:
    payload = {
        "old": old_name,
        "new": new_name,
        "summary": summarize(changes),
        "changes": [c.as_dict() for c in sorted(changes, key=_sort_key)],
    }
    return json.dumps(payload, indent=2) + "\n"


RENDERERS = {
    "text": render_text,
    "markdown": render_markdown,
    "json": render_json,
}
