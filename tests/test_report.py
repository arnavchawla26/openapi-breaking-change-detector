import json

from oadiff.change import Change, Severity
from oadiff.report import render_json, render_markdown, render_text, summarize


CHANGES = [
    Change(Severity.BREAKING, "operation-removed", "DELETE", "/pets/{id}", "", "DELETE /pets/{id} was removed"),
    Change(Severity.NON_BREAKING, "operation-added", "GET", "/health", "", "GET /health was added"),
    Change(Severity.UNKNOWN, "composition-changed", "POST", "/pets", "requestBody", "oneOf added"),
]


def test_summarize_counts():
    counts = summarize(CHANGES)
    assert counts["breaking"] == 1
    assert counts["non-breaking"] == 1
    assert counts["unknown"] == 1
    assert counts["total"] == 3


def test_summarize_empty():
    counts = summarize([])
    assert counts["total"] == 0
    assert counts["breaking"] == 0


def test_render_text_contains_all_messages():
    text = render_text(CHANGES, "old.yaml", "new.yaml")
    assert "old.yaml -> new.yaml" in text
    assert "DELETE /pets/{id} was removed" in text
    assert "GET /health was added" in text
    assert "BREAKING" in text


def test_render_text_no_changes():
    text = render_text([], "a", "b")
    assert "No differences found." in text


def test_render_markdown_has_sections():
    md = render_markdown(CHANGES, "old.yaml", "new.yaml")
    assert md.startswith("# API diff:")
    assert "## BREAKING (1)" in md
    assert "## non-breaking (1)" in md
    assert "## needs review (1)" in md
    assert "| Endpoint | Location | Change |" in md


def test_render_markdown_escapes_pipe_in_message():
    changes = [Change(Severity.BREAKING, "x", "GET", "/x", "", "message | with pipe")]
    md = render_markdown(changes, "a", "b")
    assert "message \\| with pipe" in md


def test_render_json_round_trips():
    payload = json.loads(render_json(CHANGES, "old.yaml", "new.yaml"))
    assert payload["old"] == "old.yaml"
    assert payload["new"] == "new.yaml"
    assert payload["summary"]["total"] == 3
    assert len(payload["changes"]) == 3
    kinds = {c["kind"] for c in payload["changes"]}
    assert kinds == {"operation-removed", "operation-added", "composition-changed"}


def test_render_json_sorted_breaking_first():
    payload = json.loads(render_json(CHANGES, "a", "b"))
    severities = [c["severity"] for c in payload["changes"]]
    assert severities[0] == "breaking"
