from oadiff.change import Severity
from oadiff.diff import diff_specs
from oadiff.normalize import normalize


def _base_spec():
    return {
        "paths": {
            "/pets": {
                "get": {
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created", "content": {}}},
                },
            }
        }
    }


def _kinds_by_path(changes, path, method=None):
    return {c.kind for c in changes if c.path == path and (method is None or c.method == method)}


def test_identical_specs_have_no_changes():
    spec = _base_spec()
    old = normalize(spec)
    new = normalize(spec)
    assert diff_specs(old, new) == []


def test_removed_operation_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    del new_raw["paths"]["/pets"]["post"]
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    removed = [c for c in changes if c.kind == "operation-removed"]
    assert len(removed) == 1
    assert removed[0].severity == Severity.BREAKING
    assert removed[0].method == "POST"


def test_added_path_is_non_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/health"] = {"get": {"responses": {"200": {"description": "OK", "content": {}}}}}
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    added = [c for c in changes if c.kind == "operation-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.NON_BREAKING


def test_new_required_query_param_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/pets"]["get"]["parameters"].append(
        {"name": "apiKey", "in": "query", "required": True, "schema": {"type": "string"}}
    )
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    added = [c for c in changes if c.kind == "parameter-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.BREAKING


def test_new_optional_query_param_is_non_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/pets"]["get"]["parameters"].append(
        {"name": "sort", "in": "query", "required": False, "schema": {"type": "string"}}
    )
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    added = [c for c in changes if c.kind == "parameter-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.NON_BREAKING


def test_response_field_removed_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    del new_raw["paths"]["/pets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"][
        "properties"
    ]["name"]
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    prop_removed = [c for c in changes if c.kind == "property-removed"]
    assert len(prop_removed) == 1
    assert prop_removed[0].severity == Severity.BREAKING
    assert prop_removed[0].method == "GET"
    assert "responses.200.application/json" in prop_removed[0].location


def test_request_body_became_required_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/pets"] = dict(new_raw["paths"]["/pets"])
    new_raw["paths"]["/pets"]["get"] = dict(new_raw["paths"]["/pets"]["get"])
    new_raw["paths"]["/pets"]["get"]["requestBody"] = {"required": True, "content": {}}
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    added = [c for c in changes if c.kind == "request-body-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.BREAKING


def test_response_removed_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/pets"]["post"]["responses"]["400"] = {"description": "bad", "content": {}}
    old_2 = normalize(old_raw)
    new_2 = normalize(new_raw)
    changes = diff_specs(old_2, new_2)
    added = [c for c in changes if c.kind == "response-added"]
    assert len(added) == 1
    assert added[0].severity == Severity.NON_BREAKING

    changes_reverse = diff_specs(new_2, old_2)
    removed = [c for c in changes_reverse if c.kind == "response-removed"]
    assert len(removed) == 1
    assert removed[0].severity == Severity.BREAKING


def test_parameter_becomes_required_is_breaking():
    old_raw = _base_spec()
    new_raw = _base_spec()
    new_raw["paths"]["/pets"]["get"]["parameters"][0]["required"] = True
    old, new = normalize(old_raw), normalize(new_raw)
    changes = diff_specs(old, new)
    flagged = [c for c in changes if c.kind == "parameter-required-added"]
    assert len(flagged) == 1
    assert flagged[0].severity == Severity.BREAKING


def test_full_diff_is_symmetric_in_operation_coverage():
    old_raw = _base_spec()
    new_raw = _base_spec()
    del new_raw["paths"]["/pets"]["post"]
    old, new = normalize(old_raw), normalize(new_raw)
    forward = diff_specs(old, new)
    backward = diff_specs(new, old)
    assert any(c.kind == "operation-removed" for c in forward)
    assert any(c.kind == "operation-added" for c in backward)
