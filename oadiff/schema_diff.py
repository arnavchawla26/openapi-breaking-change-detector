"""Recursive comparison of two (already $ref-resolved) JSON-Schema-ish
objects, producing a list of :class:`~oadiff.change.Change` records.

The classification of "is this breaking?" depends on which direction data
flows:

* ``direction="request"``: the schema describes data a *client* sends to the
  server (request body, or a parameter's schema). A change is breaking when
  requests that were valid before are no longer accepted.
* ``direction="response"``: the schema describes data the *server* sends to
  a client (response body). A change is breaking when responses that were
  valid before might no longer be understood/handled correctly by an
  existing client.

See the README for the full rule table this module implements.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .change import Change, Severity

_MAX_DEPTH = 40


def diff_schemas(
    old: Any,
    new: Any,
    direction: str,
    method: str,
    path: str,
    location_prefix: str,
) -> List[Change]:
    changes: List[Change] = []
    _diff(old, new, direction, method, path, location_prefix, changes, depth=0)
    return changes


def _emit(changes, severity, kind, method, path, location, message):
    changes.append(Change(severity, kind, method, path, location, message))


def _diff(old, new, direction, method, path, loc, changes, depth):
    if depth > _MAX_DEPTH:
        return
    if old is None and new is None:
        return
    if old is None:
        # schema newly introduced where there was none before (e.g. a param
        # gained an explicit schema). Treat as informational, not breaking.
        return
    if new is None:
        _emit(
            changes, Severity.UNKNOWN, "schema-removed", method, path, loc,
            f"{loc or '(root)'}: schema was removed entirely",
        )
        return
    if not isinstance(old, dict) or not isinstance(new, dict):
        if old != new:
            _emit(
                changes, Severity.UNKNOWN, "schema-malformed", method, path, loc,
                f"{loc or '(root)'}: schema is not an object in old or new spec",
            )
        return

    if "$circular_ref" in old or "$circular_ref" in new:
        old_ref = old.get("$circular_ref")
        new_ref = new.get("$circular_ref")
        if old_ref != new_ref:
            _emit(
                changes, Severity.UNKNOWN, "schema-circular-ref-changed", method, path, loc,
                f"{loc or '(root)'}: circular schema reference target changed",
            )
        return

    _diff_type(old, new, direction, method, path, loc, changes)
    _diff_format(old, new, direction, method, path, loc, changes)
    _diff_nullable(old, new, direction, method, path, loc, changes)
    _diff_enum(old, new, direction, method, path, loc, changes)
    _diff_required(old, new, direction, method, path, loc, changes)
    _diff_properties(old, new, direction, method, path, loc, changes, depth)
    _diff_additional_properties(old, new, direction, method, path, loc, changes)
    _diff_items(old, new, direction, method, path, loc, changes, depth)
    _diff_composition(old, new, direction, method, path, loc, changes)


def _types_of(schema: dict) -> Optional[set]:
    t = schema.get("type")
    if t is None:
        return None
    if isinstance(t, list):
        return set(t)
    return {t}


def _diff_type(old, new, direction, method, path, loc, changes):
    old_types = _types_of(old)
    new_types = _types_of(new)
    if old_types is None or new_types is None:
        return
    if old_types != new_types:
        _emit(
            changes, Severity.BREAKING, "schema-type-changed", method, path, loc,
            f"{loc or '(root)'}: type changed from {_fmt(old_types)} to {_fmt(new_types)}",
        )


def _diff_format(old, new, direction, method, path, loc, changes):
    old_fmt, new_fmt = old.get("format"), new.get("format")
    if old_fmt and new_fmt and old_fmt != new_fmt:
        _emit(
            changes, Severity.BREAKING, "schema-format-changed", method, path, loc,
            f"{loc or '(root)'}: format changed from {old_fmt!r} to {new_fmt!r}",
        )
    elif old_fmt and not new_fmt:
        _emit(
            changes, Severity.NON_BREAKING, "schema-format-removed", method, path, loc,
            f"{loc or '(root)'}: format constraint {old_fmt!r} removed (now less strict)",
        )
    elif new_fmt and not old_fmt:
        severity = Severity.BREAKING if direction == "request" else Severity.NON_BREAKING
        _emit(
            changes, severity, "schema-format-added", method, path, loc,
            f"{loc or '(root)'}: format constraint {new_fmt!r} added",
        )


def _diff_nullable(old, new, direction, method, path, loc, changes):
    old_n = bool(old.get("nullable", False))
    new_n = bool(new.get("nullable", False))
    if old_n and not new_n:
        severity = Severity.BREAKING if direction == "request" else Severity.BREAKING
        _emit(
            changes, severity, "schema-nullable-removed", method, path, loc,
            f"{loc or '(root)'}: no longer nullable (null was previously allowed)",
        )
    elif new_n and not old_n:
        severity = Severity.NON_BREAKING if direction == "request" else Severity.BREAKING
        _emit(
            changes, severity, "schema-nullable-added", method, path, loc,
            f"{loc or '(root)'}: now nullable (null is a newly allowed value)",
        )


def _diff_enum(old, new, direction, method, path, loc, changes):
    old_enum, new_enum = old.get("enum"), new.get("enum")
    if not isinstance(old_enum, list) or not isinstance(new_enum, list):
        return
    old_set, new_set = set(map(_hashable, old_enum)), set(map(_hashable, new_enum))
    removed = old_set - new_set
    added = new_set - old_set
    if removed:
        severity = Severity.BREAKING if direction == "request" else Severity.NON_BREAKING
        _emit(
            changes, severity, "enum-value-removed", method, path, loc,
            f"{loc or '(root)'}: enum value(s) removed: {_fmt(removed)}",
        )
    if added:
        severity = Severity.NON_BREAKING if direction == "request" else Severity.BREAKING
        _emit(
            changes, severity, "enum-value-added", method, path, loc,
            f"{loc or '(root)'}: enum value(s) added: {_fmt(added)}",
        )


def _diff_required(old, new, direction, method, path, loc, changes):
    old_req = set(old.get("required") or []) if isinstance(old.get("required"), list) else set()
    new_req = set(new.get("required") or []) if isinstance(new.get("required"), list) else set()
    added = new_req - old_req
    removed = old_req - new_req
    for field_name in sorted(added):
        severity = Severity.BREAKING if direction == "request" else Severity.NON_BREAKING
        _emit(
            changes, severity, "required-field-added", method, path,
            f"{loc}.required" if loc else "required",
            f"field {field_name!r} is now required",
        )
    for field_name in sorted(removed):
        severity = Severity.NON_BREAKING if direction == "request" else Severity.BREAKING
        _emit(
            changes, severity, "required-field-removed", method, path,
            f"{loc}.required" if loc else "required",
            f"field {field_name!r} is no longer required",
        )


def _diff_properties(old, new, direction, method, path, loc, changes, depth):
    old_props = old.get("properties")
    new_props = new.get("properties")
    if not isinstance(old_props, dict) and not isinstance(new_props, dict):
        return
    old_props = old_props or {}
    new_props = new_props or {}
    new_required = set(new.get("required") or []) if isinstance(new.get("required"), list) else set()
    old_required = set(old.get("required") or []) if isinstance(old.get("required"), list) else set()

    for name in sorted(set(old_props) - set(new_props)):
        was_required = name in old_required
        if direction == "response":
            severity = Severity.BREAKING
        else:
            severity = Severity.NON_BREAKING
        field_loc = f"{loc}.properties.{name}" if loc else f"properties.{name}"
        _emit(
            changes, severity, "property-removed", method, path, field_loc,
            f"property {name!r} removed"
            + (" (was required)" if was_required and direction == "response" else ""),
        )

    for name in sorted(set(new_props) - set(old_props)):
        is_required = name in new_required
        field_loc = f"{loc}.properties.{name}" if loc else f"properties.{name}"
        if direction == "request":
            severity = Severity.BREAKING if is_required else Severity.NON_BREAKING
        else:
            severity = Severity.NON_BREAKING
        _emit(
            changes, severity, "property-added", method, path, field_loc,
            f"property {name!r} added" + (" (required)" if is_required else ""),
        )

    for name in sorted(set(old_props) & set(new_props)):
        field_loc = f"{loc}.properties.{name}" if loc else f"properties.{name}"
        _diff(old_props[name], new_props[name], direction, method, path, field_loc, changes, depth + 1)


def _diff_additional_properties(old, new, direction, method, path, loc, changes):
    old_ap = old.get("additionalProperties", True)
    new_ap = new.get("additionalProperties", True)
    old_closed = old_ap is False
    new_closed = new_ap is False
    if new_closed and not old_closed:
        severity = Severity.BREAKING if direction == "request" else Severity.NON_BREAKING
        _emit(
            changes, severity, "additional-properties-disallowed", method, path,
            f"{loc}.additionalProperties" if loc else "additionalProperties",
            "additionalProperties is now false (extra fields no longer allowed)",
        )
    elif old_closed and not new_closed:
        severity = Severity.NON_BREAKING if direction == "request" else Severity.BREAKING
        _emit(
            changes, severity, "additional-properties-allowed", method, path,
            f"{loc}.additionalProperties" if loc else "additionalProperties",
            "additionalProperties is no longer false (extra fields now allowed)",
        )


def _diff_items(old, new, direction, method, path, loc, changes, depth):
    old_items, new_items = old.get("items"), new.get("items")
    if old_items is None and new_items is None:
        return
    item_loc = f"{loc}.items" if loc else "items"
    _diff(old_items, new_items, direction, method, path, item_loc, changes, depth + 1)


def _diff_composition(old, new, direction, method, path, loc, changes):
    for keyword in ("oneOf", "anyOf", "allOf"):
        old_has = keyword in old
        new_has = keyword in new
        if old_has != new_has:
            _emit(
                changes, Severity.UNKNOWN, "composition-changed", method, path, loc,
                f"{loc or '(root)'}: {keyword!r} was "
                + ("added" if new_has else "removed")
                + " -- review manually, composition schemas are not deeply diffed in v1",
            )


def _hashable(value):
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def _fmt(value) -> str:
    if isinstance(value, (set, frozenset)):
        return ", ".join(repr(v) for v in sorted(value, key=str))
    return repr(value)
