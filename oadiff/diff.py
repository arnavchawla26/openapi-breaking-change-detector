"""Top-level diff: compare two normalized specs and produce the full list of
:class:`~oadiff.change.Change` records (paths, operations, parameters,
request bodies, responses -- delegating schema-shape comparison to
:mod:`oadiff.schema_diff`)."""

from __future__ import annotations

from typing import List

from .change import Change, Severity
from .normalize import NormalizedSpec, Operation
from .schema_diff import diff_schemas


def diff_specs(old: NormalizedSpec, new: NormalizedSpec) -> List[Change]:
    changes: List[Change] = []

    old_keys = set(old.operations)
    new_keys = set(new.operations)

    for key in sorted(old_keys - new_keys):
        op = old.operations[key]
        changes.append(
            Change(
                Severity.BREAKING, "operation-removed", op.method, op.path, "",
                f"{op.method} {op.path} was removed",
            )
        )

    for key in sorted(new_keys - old_keys):
        op = new.operations[key]
        changes.append(
            Change(
                Severity.NON_BREAKING, "operation-added", op.method, op.path, "",
                f"{op.method} {op.path} was added",
            )
        )

    for key in sorted(old_keys & new_keys):
        changes.extend(_diff_operation(old.operations[key], new.operations[key]))

    return changes


def _diff_operation(old_op: Operation, new_op: Operation) -> List[Change]:
    changes: List[Change] = []
    method, path = old_op.method, old_op.path

    changes.extend(_diff_parameters(old_op, new_op))
    changes.extend(_diff_request_body(old_op, new_op))
    changes.extend(_diff_responses(old_op, new_op))
    return changes


def _diff_parameters(old_op: Operation, new_op: Operation) -> List[Change]:
    changes: List[Change] = []
    method, path = old_op.method, old_op.path
    old_params, new_params = old_op.parameters, new_op.parameters

    for key in sorted(set(old_params) - set(new_params)):
        p = old_params[key]
        severity = Severity.BREAKING if p.required else Severity.NON_BREAKING
        changes.append(
            Change(
                severity, "parameter-removed", method, path, f"parameters.{key}",
                f"parameter {p.name!r} ({p.location}) removed"
                + (" (was required)" if p.required else " (was optional)"),
            )
        )

    for key in sorted(set(new_params) - set(old_params)):
        p = new_params[key]
        severity = Severity.BREAKING if p.required else Severity.NON_BREAKING
        changes.append(
            Change(
                severity, "parameter-added", method, path, f"parameters.{key}",
                f"parameter {p.name!r} ({p.location}) added"
                + (" (required)" if p.required else " (optional)"),
            )
        )

    for key in sorted(set(old_params) & set(new_params)):
        old_p, new_p = old_params[key], new_params[key]
        loc = f"parameters.{key}"
        if old_p.required != new_p.required:
            if new_p.required and not old_p.required:
                changes.append(
                    Change(
                        Severity.BREAKING, "parameter-required-added", method, path, loc,
                        f"parameter {new_p.name!r} became required",
                    )
                )
            else:
                changes.append(
                    Change(
                        Severity.NON_BREAKING, "parameter-required-removed", method, path, loc,
                        f"parameter {new_p.name!r} is no longer required",
                    )
                )
        changes.extend(
            diff_schemas(old_p.schema, new_p.schema, "request", method, path, f"{loc}.schema")
        )

    return changes


def _diff_request_body(old_op: Operation, new_op: Operation) -> List[Change]:
    changes: List[Change] = []
    method, path = old_op.method, old_op.path
    old_rb, new_rb = old_op.request_body, new_op.request_body

    if old_rb is None and new_rb is None:
        return changes
    if old_rb is None and new_rb is not None:
        severity = Severity.BREAKING if new_rb.required else Severity.NON_BREAKING
        changes.append(
            Change(
                severity, "request-body-added", method, path, "requestBody",
                "request body added" + (" (required)" if new_rb.required else " (optional)"),
            )
        )
        return changes
    if old_rb is not None and new_rb is None:
        changes.append(
            Change(
                Severity.BREAKING, "request-body-removed", method, path, "requestBody",
                "request body removed",
            )
        )
        return changes

    if not old_rb.required and new_rb.required:
        changes.append(
            Change(
                Severity.BREAKING, "request-body-required-added", method, path, "requestBody",
                "request body became required",
            )
        )
    elif old_rb.required and not new_rb.required:
        changes.append(
            Change(
                Severity.NON_BREAKING, "request-body-required-removed", method, path, "requestBody",
                "request body is no longer required",
            )
        )

    old_types, new_types = set(old_rb.content), set(new_rb.content)
    for media_type in sorted(old_types - new_types):
        changes.append(
            Change(
                Severity.BREAKING, "request-content-type-removed", method, path,
                f"requestBody.{media_type}",
                f"request content type {media_type!r} removed",
            )
        )
    for media_type in sorted(new_types - old_types):
        changes.append(
            Change(
                Severity.NON_BREAKING, "request-content-type-added", method, path,
                f"requestBody.{media_type}",
                f"request content type {media_type!r} added",
            )
        )
    for media_type in sorted(old_types & new_types):
        changes.extend(
            diff_schemas(
                old_rb.content[media_type], new_rb.content[media_type], "request",
                method, path, f"requestBody.{media_type}",
            )
        )

    return changes


def _diff_responses(old_op: Operation, new_op: Operation) -> List[Change]:
    changes: List[Change] = []
    method, path = old_op.method, old_op.path
    old_resp, new_resp = old_op.responses, new_op.responses

    for status in sorted(set(old_resp) - set(new_resp)):
        changes.append(
            Change(
                Severity.BREAKING, "response-removed", method, path, f"responses.{status}",
                f"response {status} removed",
            )
        )
    for status in sorted(set(new_resp) - set(old_resp)):
        changes.append(
            Change(
                Severity.NON_BREAKING, "response-added", method, path, f"responses.{status}",
                f"response {status} added",
            )
        )

    for status in sorted(set(old_resp) & set(new_resp)):
        old_r, new_r = old_resp[status], new_resp[status]
        old_types, new_types = set(old_r.content), set(new_r.content)
        for media_type in sorted(old_types - new_types):
            changes.append(
                Change(
                    Severity.BREAKING, "response-content-type-removed", method, path,
                    f"responses.{status}.{media_type}",
                    f"response {status} content type {media_type!r} removed",
                )
            )
        for media_type in sorted(new_types - old_types):
            changes.append(
                Change(
                    Severity.NON_BREAKING, "response-content-type-added", method, path,
                    f"responses.{status}.{media_type}",
                    f"response {status} content type {media_type!r} added",
                )
            )
        for media_type in sorted(old_types & new_types):
            changes.extend(
                diff_schemas(
                    old_r.content[media_type], new_r.content[media_type], "response",
                    method, path, f"responses.{status}.{media_type}",
                )
            )

    return changes
