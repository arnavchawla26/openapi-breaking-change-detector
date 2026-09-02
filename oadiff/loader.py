"""Load an OpenAPI/Swagger document from a JSON or YAML file."""

from __future__ import annotations

import json
import os
from typing import Any

from .yaml_subset import YamlSubsetError, loads as yaml_loads


class SpecLoadError(ValueError):
    """Raised when a spec file cannot be parsed as JSON or the supported YAML subset."""


def load_spec(path: str) -> Any:
    """Load a spec from ``path``, choosing a parser by extension with a fallback.

    ``.json`` files are parsed as JSON. ``.yaml``/``.yml`` files are parsed with
    :mod:`oadiff.yaml_subset`. Any other extension (or none) tries JSON first,
    then falls back to the YAML subset parser, since OpenAPI files are
    sometimes extensionless or use e.g. ``.txt``.
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return load_spec_text(text, hint=os.path.splitext(path)[1].lower(), source=path)


def load_spec_text(text: str, hint: str = "", source: str = "<string>") -> Any:
    if hint == ".json":
        return _parse_json(text, source)
    if hint in (".yaml", ".yml"):
        return _parse_yaml(text, source)

    try:
        return _parse_json(text, source)
    except SpecLoadError:
        pass
    return _parse_yaml(text, source)


def _parse_json(text: str, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecLoadError(f"{source}: invalid JSON ({exc})") from exc


def _parse_yaml(text: str, source: str) -> Any:
    try:
        return yaml_loads(text)
    except YamlSubsetError as exc:
        raise SpecLoadError(
            f"{source}: could not parse as JSON or the supported YAML subset ({exc})"
        ) from exc
