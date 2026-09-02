import json
import os

import pytest

from oadiff.loader import SpecLoadError, load_spec, load_spec_text


def test_load_json_file(tmp_path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"openapi": "3.0.0"}))
    assert load_spec(str(p)) == {"openapi": "3.0.0"}


def test_load_yaml_file(tmp_path):
    p = tmp_path / "spec.yaml"
    p.write_text("openapi: 3.0.0\ninfo:\n  title: X\n")
    result = load_spec(str(p))
    assert result["openapi"] == "3.0.0"
    assert result["info"]["title"] == "X"


def test_load_yml_extension(tmp_path):
    p = tmp_path / "spec.yml"
    p.write_text("a: 1\n")
    assert load_spec(str(p)) == {"a": 1}


def test_extensionless_falls_back_to_yaml(tmp_path):
    p = tmp_path / "spec"
    p.write_text("a: 1\nb: 2\n")
    assert load_spec(str(p)) == {"a": 1, "b": 2}


def test_extensionless_json(tmp_path):
    p = tmp_path / "spec"
    p.write_text('{"a": 1}')
    assert load_spec(str(p)) == {"a": 1}


def test_invalid_json_extension_raises():
    with pytest.raises(SpecLoadError):
        load_spec_text("{not valid json", hint=".json")


def test_invalid_yaml_and_json_raises():
    with pytest.raises(SpecLoadError):
        load_spec_text("a:\n\tb: 1", hint=".yaml")


def test_missing_file_raises():
    with pytest.raises(OSError):
        load_spec("/nonexistent/path/spec.yaml")
