"""The ``Change`` record type shared by the schema differ and the top-level
operation differ, plus the severity enum."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    BREAKING = "breaking"
    NON_BREAKING = "non-breaking"
    UNKNOWN = "unknown"  # a change we can see but can't confidently classify


@dataclass(frozen=True)
class Change:
    severity: Severity
    kind: str  # short machine-readable category, e.g. "parameter-removed"
    method: str  # HTTP method, or "" for spec-level changes
    path: str  # OpenAPI path template, or "" for spec-level changes
    location: str  # where within the operation, e.g. "requestBody.application/json.properties.age"
    message: str  # human-readable description

    def as_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "kind": self.kind,
            "method": self.method,
            "path": self.path,
            "location": self.location,
            "message": self.message,
        }
