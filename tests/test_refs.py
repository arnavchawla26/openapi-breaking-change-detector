from oadiff.refs import resolve


def test_simple_local_ref():
    root = {
        "components": {"schemas": {"Pet": {"type": "object", "properties": {"id": {"type": "integer"}}}}}
    }
    node = {"$ref": "#/components/schemas/Pet"}
    resolved = resolve(node, root)
    assert resolved == {"type": "object", "properties": {"id": {"type": "integer"}}}


def test_nested_ref_inside_structure():
    root = {
        "components": {"schemas": {"Id": {"type": "integer"}}},
    }
    node = {"type": "object", "properties": {"id": {"$ref": "#/components/schemas/Id"}}}
    resolved = resolve(node, root)
    assert resolved == {"type": "object", "properties": {"id": {"type": "integer"}}}


def test_chained_refs():
    root = {
        "components": {
            "schemas": {
                "A": {"$ref": "#/components/schemas/B"},
                "B": {"type": "string"},
            }
        }
    }
    node = {"$ref": "#/components/schemas/A"}
    assert resolve(node, root) == {"type": "string"}


def test_circular_ref_terminates():
    root = {
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"next": {"$ref": "#/components/schemas/Node"}},
                }
            }
        }
    }
    node = {"$ref": "#/components/schemas/Node"}
    resolved = resolve(node, root)
    assert resolved["type"] == "object"
    assert resolved["properties"]["next"] == {"$circular_ref": "#/components/schemas/Node"}


def test_external_ref_left_untouched():
    node = {"$ref": "other.yaml#/Foo"}
    assert resolve(node, {}) == {"$ref": "other.yaml#/Foo"}


def test_json_pointer_escapes():
    root = {"components": {"schemas": {"a/b": {"type": "string"}}}}
    node = {"$ref": "#/components/schemas/a~1b"}
    assert resolve(node, root) == {"type": "string"}


def test_list_passthrough():
    root = {"components": {"schemas": {"S": {"type": "string"}}}}
    node = [{"$ref": "#/components/schemas/S"}, {"type": "integer"}]
    assert resolve(node, root) == [{"type": "string"}, {"type": "integer"}]
