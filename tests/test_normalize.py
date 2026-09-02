from oadiff.normalize import normalize


SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Pets", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "parameters": [{"name": "X-Trace-Id", "in": "header", "required": False, "schema": {"type": "string"}}],
            "get": {
                "operationId": "listPets",
                "parameters": [
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PetList"}
                            }
                        },
                    }
                },
            },
            "post": {
                "operationId": "createPet",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/NewPet"}}
                    },
                },
                "responses": {"201": {"description": "Created", "content": {}}},
            },
        }
    },
    "components": {
        "schemas": {
            "NewPet": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
            "PetList": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Pet"},
            },
            "Pet": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
        }
    },
}


def test_normalize_builds_operations():
    result = normalize(SPEC)
    assert result.title == "Pets"
    assert set(result.operations) == {"GET /pets", "POST /pets"}


def test_path_level_parameters_are_inherited():
    result = normalize(SPEC)
    get_op = result.operations["GET /pets"]
    assert "header:X-Trace-Id" in get_op.parameters
    assert "query:limit" in get_op.parameters


def test_refs_resolved_in_responses():
    result = normalize(SPEC)
    get_op = result.operations["GET /pets"]
    schema = get_op.responses["200"].content["application/json"]
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "object"
    assert set(schema["items"]["properties"]) == {"id", "name"}


def test_refs_resolved_in_request_body():
    result = normalize(SPEC)
    post_op = result.operations["POST /pets"]
    assert post_op.request_body.required is True
    schema = post_op.request_body.content["application/json"]
    assert schema["required"] == ["name"]


def test_operation_with_no_request_body_is_none():
    result = normalize(SPEC)
    get_op = result.operations["GET /pets"]
    assert get_op.request_body is None


def test_empty_spec():
    result = normalize({})
    assert result.operations == {}


def test_operation_level_parameter_overrides_path_level():
    spec = {
        "paths": {
            "/x": {
                "parameters": [{"name": "id", "in": "query", "required": False}],
                "get": {
                    "parameters": [{"name": "id", "in": "query", "required": True}],
                    "responses": {},
                },
            }
        }
    }
    result = normalize(spec)
    param = result.operations["GET /x"].parameters["query:id"]
    assert param.required is True
