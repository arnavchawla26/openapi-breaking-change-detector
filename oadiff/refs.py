"""Resolution of local (in-document) ``$ref`` pointers in an OpenAPI spec.

Only local refs of the form ``#/a/b/c`` are supported -- external file or URL
refs are left untouched (as a dict containing ``$ref``) since resolving them
would require network/filesystem access this tool intentionally avoids for
v1. Circular refs are detected and replaced with an opaque marker so the
schema differ can still terminate and compare "is this still pointing at the
same shape" without infinite recursion.
"""

from __future__ import annotations

from typing import Any, FrozenSet


class RefResolutionError(ValueError):
    pass


def resolve(node: Any, root: Any, seen: FrozenSet[str] = frozenset()) -> Any:
    """Recursively resolve local ``$ref`` pointers within ``node``.

    Returns a new structure with refs replaced by their resolved (and further
    resolved) targets. Non-dict/list values are returned unchanged.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/"):
                # external ref -- leave as-is, unresolved
                return dict(node)
            if ref in seen:
                return {"$circular_ref": ref}
            target = _lookup(ref, root)
            return resolve(target, root, seen | {ref})
        return {k: resolve(v, root, seen) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(item, root, seen) for item in node]
    return node


def _lookup(ref: str, root: Any) -> Any:
    parts = ref[2:].split("/") if ref != "#/" else []
    current = root
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                raise RefResolutionError(f"could not resolve {ref!r}: no index {part!r}")
        else:
            raise RefResolutionError(f"could not resolve {ref!r}: no key {part!r}")
    return current
