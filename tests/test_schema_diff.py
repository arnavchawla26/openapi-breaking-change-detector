from oadiff.change import Severity
from oadiff.schema_diff import diff_schemas


def _kinds(changes):
    return {c.kind for c in changes}


def _severities_for(changes, kind):
    return {c.severity for c in changes if c.kind == kind}


def test_no_change():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert diff_schemas(schema, schema, "request", "GET", "/x", "") == []


def test_type_changed_is_always_breaking():
    old = {"type": "string"}
    new = {"type": "integer"}
    for direction in ("request", "response"):
        changes = diff_schemas(old, new, direction, "GET", "/x", "")
        assert len(changes) == 1
        assert changes[0].severity == Severity.BREAKING
        assert changes[0].kind == "schema-type-changed"


def test_request_property_removed_is_non_breaking():
    old = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    new = {"type": "object", "properties": {"a": {"type": "string"}}}
    changes = diff_schemas(old, new, "request", "POST", "/x", "")
    assert _severities_for(changes, "property-removed") == {Severity.NON_BREAKING}


def test_response_property_removed_is_breaking():
    old = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    new = {"type": "object", "properties": {"a": {"type": "string"}}}
    changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(changes, "property-removed") == {Severity.BREAKING}


def test_response_property_added_is_non_breaking():
    old = {"type": "object", "properties": {"a": {"type": "string"}}}
    new = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(changes, "property-added") == {Severity.NON_BREAKING}


def test_request_property_added_required_is_breaking():
    old = {"type": "object", "properties": {"a": {"type": "string"}}}
    new = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["b"],
    }
    changes = diff_schemas(old, new, "request", "POST", "/x", "")
    added = [c for c in changes if c.kind == "property-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.BREAKING


def test_request_property_added_optional_is_non_breaking():
    old = {"type": "object", "properties": {"a": {"type": "string"}}}
    new = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    changes = diff_schemas(old, new, "request", "POST", "/x", "")
    assert _severities_for(changes, "property-added") == {Severity.NON_BREAKING}


def test_required_field_added_request_vs_response():
    old = {"type": "object", "properties": {"a": {"type": "string"}}, "required": []}
    new = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    req_changes = diff_schemas(old, new, "request", "POST", "/x", "")
    resp_changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(req_changes, "required-field-added") == {Severity.BREAKING}
    assert _severities_for(resp_changes, "required-field-added") == {Severity.NON_BREAKING}


def test_required_field_removed_request_vs_response():
    old = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    new = {"type": "object", "properties": {"a": {"type": "string"}}, "required": []}
    req_changes = diff_schemas(old, new, "request", "POST", "/x", "")
    resp_changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(req_changes, "required-field-removed") == {Severity.NON_BREAKING}
    assert _severities_for(resp_changes, "required-field-removed") == {Severity.BREAKING}


def test_enum_narrowed_request_breaking_response_non_breaking():
    old = {"type": "string", "enum": ["a", "b", "c"]}
    new = {"type": "string", "enum": ["a", "b"]}
    req_changes = diff_schemas(old, new, "request", "GET", "/x", "")
    resp_changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(req_changes, "enum-value-removed") == {Severity.BREAKING}
    assert _severities_for(resp_changes, "enum-value-removed") == {Severity.NON_BREAKING}


def test_enum_widened_request_non_breaking_response_breaking():
    old = {"type": "string", "enum": ["a", "b"]}
    new = {"type": "string", "enum": ["a", "b", "c"]}
    req_changes = diff_schemas(old, new, "request", "GET", "/x", "")
    resp_changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(req_changes, "enum-value-added") == {Severity.NON_BREAKING}
    assert _severities_for(resp_changes, "enum-value-added") == {Severity.BREAKING}


def test_nested_property_change_reports_full_location():
    old = {
        "type": "object",
        "properties": {
            "address": {
                "type": "object",
                "properties": {"zip": {"type": "string"}},
            }
        },
    }
    new = {
        "type": "object",
        "properties": {
            "address": {
                "type": "object",
                "properties": {"zip": {"type": "integer"}},
            }
        },
    }
    changes = diff_schemas(old, new, "response", "GET", "/x", "responses.200.application/json")
    assert len(changes) == 1
    assert changes[0].kind == "schema-type-changed"
    assert changes[0].location == "responses.200.application/json.properties.address.properties.zip"


def test_array_items_diffed():
    old = {"type": "array", "items": {"type": "string"}}
    new = {"type": "array", "items": {"type": "integer"}}
    changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert len(changes) == 1
    assert changes[0].kind == "schema-type-changed"
    assert changes[0].location == "items"


def test_additional_properties_disallowed():
    old = {"type": "object"}
    new = {"type": "object", "additionalProperties": False}
    req_changes = diff_schemas(old, new, "request", "POST", "/x", "")
    resp_changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _severities_for(req_changes, "additional-properties-disallowed") == {Severity.BREAKING}
    assert _severities_for(resp_changes, "additional-properties-disallowed") == {Severity.NON_BREAKING}


def test_circular_ref_markers_compare_equal_without_recursing():
    old = {"$circular_ref": "#/components/schemas/Node"}
    new = {"$circular_ref": "#/components/schemas/Node"}
    assert diff_schemas(old, new, "response", "GET", "/x", "") == []


def test_circular_ref_target_changed_is_flagged():
    old = {"$circular_ref": "#/components/schemas/A"}
    new = {"$circular_ref": "#/components/schemas/B"}
    changes = diff_schemas(old, new, "response", "GET", "/x", "")
    assert _kinds(changes) == {"schema-circular-ref-changed"}


def test_none_schemas_are_ignored():
    assert diff_schemas(None, None, "request", "GET", "/x", "") == []


def test_schema_removed_entirely_flagged_unknown():
    old = {"type": "string"}
    changes = diff_schemas(old, None, "response", "GET", "/x", "")
    assert len(changes) == 1
    assert changes[0].severity == Severity.UNKNOWN


def test_composition_keyword_added_flagged_for_review():
    old = {"type": "object"}
    new = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
    changes = diff_schemas(old, new, "request", "POST", "/x", "")
    assert any(c.kind == "composition-changed" and c.severity == Severity.UNKNOWN for c in changes)
