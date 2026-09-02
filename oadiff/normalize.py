"""Normalize a raw OpenAPI 3.x (or Swagger 2.0) document into a shape that is
easy and unambiguous to diff: a flat map of (method, path) -> Operation.

$ref pointers are resolved up front (see :mod:`oadiff.refs`) so the differ
never has to know or care whether two specs organize their ``components``
differently -- only the effective, consumer-visible shape matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .refs import resolve

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


@dataclass
class Parameter:
    name: str
    location: str  # "in": query/path/header/cookie
    required: bool
    schema: Any


@dataclass
class RequestBody:
    required: bool
    content: Dict[str, Any]  # media type -> resolved schema (or None)


@dataclass
class Response:
    status: str
    description: str
    content: Dict[str, Any]  # media type -> resolved schema (or None)


@dataclass
class Operation:
    method: str
    path: str
    operation_id: Optional[str]
    parameters: Dict[str, Parameter] = field(default_factory=dict)  # key: "in:name"
    request_body: Optional[RequestBody] = None
    responses: Dict[str, Response] = field(default_factory=dict)  # key: status code str


@dataclass
class NormalizedSpec:
    title: str
    version: str
    operations: Dict[str, Operation]  # key: "METHOD /path"


def normalize(raw_spec: Any) -> NormalizedSpec:
    if not isinstance(raw_spec, dict):
        raise ValueError("spec root must be a JSON/YAML object")
    resolved = resolve(raw_spec, raw_spec)

    info = resolved.get("info") or {}
    title = info.get("title", "") if isinstance(info, dict) else ""
    version = info.get("version", "") if isinstance(info, dict) else ""

    operations: Dict[str, Operation] = {}
    paths = resolved.get("paths") or {}
    if not isinstance(paths, dict):
        paths = {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_level_params = _index_parameters(path_item.get("parameters") or [])
        for method in HTTP_METHODS:
            op = path_item.get(method)
            if op is None:
                continue
            if not isinstance(op, dict):
                continue
            params = dict(path_level_params)
            params.update(_index_parameters(op.get("parameters") or []))

            request_body = _build_request_body(op.get("requestBody"))
            responses = _build_responses(op.get("responses") or {})

            operation = Operation(
                method=method.upper(),
                path=path,
                operation_id=op.get("operationId"),
                parameters=params,
                request_body=request_body,
                responses=responses,
            )
            operations[f"{method.upper()} {path}"] = operation

    return NormalizedSpec(title=title, version=version, operations=operations)


def _index_parameters(raw_params: List[Any]) -> Dict[str, Parameter]:
    result: Dict[str, Parameter] = {}
    for p in raw_params:
        if not isinstance(p, dict) or "name" not in p or "in" not in p:
            continue
        key = f"{p['in']}:{p['name']}"
        result[key] = Parameter(
            name=p["name"],
            location=p["in"],
            required=bool(p.get("required", p["in"] == "path")),
            schema=p.get("schema"),
        )
    return result


def _build_request_body(raw: Any) -> Optional[RequestBody]:
    if not isinstance(raw, dict):
        return None
    content_in = raw.get("content") or {}
    content: Dict[str, Any] = {}
    if isinstance(content_in, dict):
        for media_type, media_obj in content_in.items():
            schema = media_obj.get("schema") if isinstance(media_obj, dict) else None
            content[media_type] = schema
    return RequestBody(required=bool(raw.get("required", False)), content=content)


def _build_responses(raw: Dict[str, Any]) -> Dict[str, Response]:
    result: Dict[str, Response] = {}
    if not isinstance(raw, dict):
        return result
    for status, resp_obj in raw.items():
        if not isinstance(resp_obj, dict):
            continue
        content_in = resp_obj.get("content") or {}
        content: Dict[str, Any] = {}
        if isinstance(content_in, dict):
            for media_type, media_obj in content_in.items():
                schema = media_obj.get("schema") if isinstance(media_obj, dict) else None
                content[media_type] = schema
        result[str(status)] = Response(
            status=str(status),
            description=resp_obj.get("description", ""),
            content=content,
        )
    return result
