import json
import os
import subprocess
import sys

import pytest

from oadiff.cli import main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
V1 = os.path.join(FIXTURES, "petstore_v1.yaml")
V2 = os.path.join(FIXTURES, "petstore_v2_breaking.yaml")


def test_identical_spec_no_changes(capsys):
    code = main([V1, V1])
    out = capsys.readouterr().out
    assert code == 0
    assert "No differences found." in out


def test_breaking_changes_detected_text(capsys):
    code = main([V1, V2])
    out = capsys.readouterr().out
    assert code == 0  # --fail-on-breaking not passed
    assert "BREAKING" in out
    assert "apiKey" in out


def test_fail_on_breaking_sets_exit_code(capsys):
    code = main([V1, V2, "--fail-on-breaking"])
    capsys.readouterr()
    assert code == 1


def test_fail_on_breaking_with_no_breaking_changes(capsys):
    code = main([V1, V1, "--fail-on-breaking"])
    capsys.readouterr()
    assert code == 0


def test_json_output_is_valid_and_has_breaking_changes(capsys):
    code = main([V1, V2, "--format", "json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["summary"]["breaking"] > 0
    kinds = {c["kind"] for c in payload["changes"]}
    assert "schema-type-changed" in kinds
    assert "parameter-added" in kinds


def test_markdown_output(capsys):
    code = main([V1, V2, "--format", "markdown"])
    out = capsys.readouterr().out
    assert out.startswith("# API diff:")
    assert "## BREAKING" in out


def test_only_breaking_filters_non_breaking(capsys):
    code = main([V1, V2, "--format", "json", "--only-breaking"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert all(c["severity"] in ("breaking", "unknown") for c in payload["changes"])


def test_output_to_file(tmp_path, capsys):
    out_file = tmp_path / "report.txt"
    code = main([V1, V2, "--output", str(out_file)])
    captured = capsys.readouterr().out
    assert captured == ""
    assert out_file.exists()
    content = out_file.read_text()
    assert "BREAKING" in content


def test_missing_file_returns_exit_code_2(capsys):
    code = main(["/nonexistent/old.yaml", V2])
    err = capsys.readouterr().err
    assert code == 2
    assert "error" in err


def test_malformed_spec_returns_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a:\n\tb: 1\n")
    code = main([str(bad), V2])
    err = capsys.readouterr().err
    assert code == 2


def test_json_vs_yaml_specs_are_equivalent(tmp_path, capsys):
    # convert v1 fixture to JSON and confirm diffing json-vs-yaml is a no-op
    from oadiff.loader import load_spec

    spec = load_spec(V1)
    json_path = tmp_path / "petstore_v1.json"
    json_path.write_text(json.dumps(spec))
    code = main([V1, str(json_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "No differences found." in out


def test_real_console_script_end_to_end():
    # Exercise the actual installed `oadiff` entry point via subprocess -- no
    # mocking of argparse, stdout, or file I/O.
    result = subprocess.run(
        [sys.executable, "-m", "oadiff.cli", V1, V2, "--format", "json", "--fail-on-breaking"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["breaking"] > 0


def test_real_console_script_identical_specs_exit_zero():
    result = subprocess.run(
        [sys.executable, "-m", "oadiff.cli", V1, V1, "--fail-on-breaking"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode == 0
    assert "No differences found." in result.stdout


def test_version_flag():
    result = subprocess.run(
        [sys.executable, "-m", "oadiff.cli", "--version"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode == 0
    assert "oadiff" in result.stdout
