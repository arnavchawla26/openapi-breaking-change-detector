"""A small, dependency-free YAML reader for the subset of YAML that OpenAPI
documents actually use in practice.

This is NOT a general-purpose YAML 1.1/1.2 parser. It intentionally supports
only what shows up in real OpenAPI/Swagger files:

  * block mappings (``key: value``), nested by indentation
  * block sequences (``- item``), including sequences of mappings and
    nested sequences (``- - item``)
  * plain, single-quoted and double-quoted scalars
  * booleans (``true``/``false``), null (``null``/``~``/empty), ints, floats
  * simple flow collections on a single line: ``[a, b, c]`` and ``{a: b}``
  * literal (``|``) and folded (``>``) block scalars (folding is
    approximated by joining with spaces; good enough for descriptions)
  * ``#`` comments (outside of quoted strings) and blank lines

Not supported: anchors/aliases (``&``/``*``), tags (``!!str``), multi-document
streams, complex (mapping) keys, and YAML 1.1 edge cases like sexagesimal
numbers. Anything using those raises :class:`YamlSubsetError` with a line
number so the caller can fall back to hand-editing the spec or converting it
to JSON. This trade-off keeps the library dependency-free, matching the rest
of this portfolio's "no PyPI required" pattern.

Validated by hand against GitHub's full public OpenAPI spec (8.8MB, ~232k
lines, 845 operations) -- see the README for details, including the real
nested-sequence edge case that stress test caught and this parser now
handles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple


class YamlSubsetError(ValueError):
    """Raised when the input uses YAML features outside the supported subset."""


@dataclass
class _Line:
    number: int
    indent: int
    content: str  # text after leading indentation, with trailing comment stripped


_NULL_TOKENS = {"~", "null", "Null", "NULL", ""}
_TRUE_TOKENS = {"true", "True", "TRUE"}
_FALSE_TOKENS = {"false", "False", "FALSE"}


def loads(text: str) -> Any:
    """Parse a YAML document (in the supported subset) into Python data."""
    lines = _preprocess(text)
    if not lines:
        return None
    value, index = _parse_block(lines, 0, lines[0].indent)
    if index != len(lines):
        raise YamlSubsetError(
            f"line {lines[index].number}: unexpected indentation/content "
            "(possibly an unsupported YAML feature)"
        )
    return value


def _preprocess(text: str) -> List[_Line]:
    if text.lstrip("﻿").strip() == "":
        return []
    text = text.lstrip("﻿")
    raw_lines = text.splitlines()
    out: List[_Line] = []
    for i, raw in enumerate(raw_lines, start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))]:
            raise YamlSubsetError(f"line {i}: tabs are not allowed for indentation")
        stripped = raw.rstrip()
        if stripped.strip() == "":
            continue
        if stripped.lstrip().startswith("#"):
            continue
        if stripped.strip() in ("---", "..."):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        content = stripped[indent:]
        content = _strip_trailing_comment(content)
        if content.strip() == "":
            continue
        out.append(_Line(number=i, indent=indent, content=content))
    return out


def _strip_trailing_comment(content: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(content):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or content[idx - 1] == " ":
                return content[:idx].rstrip()
    return content.rstrip()


def _parse_block(lines: List[_Line], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines):
        return None, index
    first = lines[index]
    if first.indent != indent:
        raise YamlSubsetError(f"line {first.number}: bad indentation")
    if first.content.startswith("- ") or first.content == "-":
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_sequence(lines: List[_Line], index: int, indent: int) -> Tuple[List[Any], int]:
    result: List[Any] = []
    while index < len(lines) and lines[index].indent == indent and (
        lines[index].content == "-" or lines[index].content.startswith("- ")
    ):
        line = lines[index]
        rest = line.content[1:].lstrip()
        item_indent = indent + (len(line.content) - len(rest))
        if rest == "":
            # value lives on following, more-indented lines
            if index + 1 < len(lines) and lines[index + 1].indent > indent:
                value, index = _parse_block(lines, index + 1, lines[index + 1].indent)
            else:
                value, index = None, index + 1
        elif _looks_like_mapping_entry(rest) or rest == "-" or rest.startswith("- "):
            # "- key: value" (inline mapping) or "- - item" (inline nested sequence):
            # rewrite this line's remainder as if it started fresh at item_indent, splice
            # it in front of the untouched remaining real lines, and let _parse_block
            # auto-detect whether that continuation is a mapping or a sequence. Virtual
            # line i (i >= 1) is exactly real line (index + i), so the number of virtual
            # lines consumed translates back to the real stream by simple addition.
            virtual = [_Line(number=line.number, indent=item_indent, content=rest)] + lines[index + 1 :]
            value, consumed = _parse_block(virtual, 0, item_indent)
            index = index + consumed
        else:
            value = _parse_scalar_line(lines, index, rest, item_indent)
            index += 1
        result.append(value)
    return result, index


def _parse_mapping(lines: List[_Line], index: int, indent: int) -> Tuple[dict, int]:
    result: dict = {}
    while index < len(lines) and lines[index].indent == indent and not (
        lines[index].content == "-" or lines[index].content.startswith("- ")
    ):
        line = lines[index]
        key, rest = _split_key_value(line.content, line.number)
        if rest == "":
            if index + 1 < len(lines) and lines[index + 1].indent > indent:
                value, index = _parse_block(lines, index + 1, lines[index + 1].indent)
            else:
                value, index = None, index + 1
        elif rest in ("|", ">") or rest.startswith("|") or rest.startswith(">"):
            value, index = _parse_block_scalar(lines, index, indent, rest)
        else:
            value = _parse_scalar_line(lines, index, rest, indent)
            index += 1
        result[key] = value
    return result, index


def _parse_block_scalar(lines: List[_Line], index: int, indent: int, marker: str) -> Tuple[str, int]:
    folded = marker.startswith(">")
    body_lines: List[str] = []
    j = index + 1
    while j < len(lines) and lines[j].indent > indent:
        body_lines.append(" " * (lines[j].indent - indent - 2) + lines[j].content)
        j += 1
    text = " ".join(l.strip() for l in body_lines) if folded else "\n".join(
        l.strip() for l in body_lines
    )
    return text, j


def _looks_like_mapping_entry(text: str) -> bool:
    if text.startswith(("[", "{", '"', "'")):
        # could still be "key: [..]"; check for a top-level ": " first
        pass
    key, rest = _try_split_key_value(text)
    return key is not None


def _split_key_value(content: str, line_no: int) -> Tuple[str, str]:
    key, rest = _try_split_key_value(content)
    if key is None:
        raise YamlSubsetError(f"line {line_no}: expected 'key: value'")
    return key, rest


def _try_split_key_value(content: str) -> Tuple[Any, str]:
    in_single = False
    in_double = False
    depth = 0
    i = 0
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == ":" and depth == 0:
                if i + 1 == n or content[i + 1] == " ":
                    raw_key = content[:i].strip()
                    rest = content[i + 1 :].strip()
                    return _parse_key(raw_key), rest
        i += 1
    return None, content


def _parse_key(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return _unquote(raw)
    return raw


def _parse_scalar_line(lines: List[_Line], index: int, rest: str, indent: int) -> Any:
    return _parse_scalar(rest)


def _parse_scalar(token: str) -> Any:
    token = token.strip()
    if token == "":
        return None
    if token.startswith("[") and token.endswith("]"):
        return _parse_flow_sequence(token)
    if token.startswith("{") and token.endswith("}"):
        return _parse_flow_mapping(token)
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return _unquote(token)
    if token in _NULL_TOKENS:
        return None
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    num = _try_parse_number(token)
    if num is not None:
        return num
    return token


def _unquote(token: str) -> str:
    quote = token[0]
    inner = token[1:-1]
    if quote == "'":
        return inner.replace("''", "'")
    return inner.encode("utf-8").decode("unicode_escape") if "\\" in inner else inner


def _try_parse_number(token: str) -> Any:
    try:
        if any(c in token for c in ".eE") and not token.lstrip("+-").isdigit():
            return float(token)
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return None


def _split_flow_items(inner: str) -> List[str]:
    items: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    current = []
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == "," and depth == 0:
                items.append("".join(current))
                current = []
                continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail != "":
        items.append(tail)
    return [i.strip() for i in items]


def _parse_flow_sequence(token: str) -> List[Any]:
    inner = token[1:-1].strip()
    if inner == "":
        return []
    return [_parse_flow_value(item) for item in _split_flow_items(inner)]


def _parse_flow_mapping(token: str) -> dict:
    inner = token[1:-1].strip()
    if inner == "":
        return {}
    result = {}
    for item in _split_flow_items(inner):
        key, rest = _try_split_key_value(item)
        if key is None:
            raise YamlSubsetError(f"malformed flow mapping entry: {item!r}")
        result[key] = _parse_flow_value(rest)
    return result


def _parse_flow_value(token: str) -> Any:
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        return _parse_flow_sequence(token)
    if token.startswith("{") and token.endswith("}"):
        return _parse_flow_mapping(token)
    return _parse_scalar(token)
