import pytest

from oadiff.yaml_subset import YamlSubsetError, loads


def test_simple_mapping():
    assert loads("a: 1\nb: 2\n") == {"a": 1, "b": 2}


def test_nested_mapping():
    text = """
a:
  b: 1
  c: 2
d: 3
"""
    assert loads(text) == {"a": {"b": 1, "c": 2}, "d": 3}


def test_sequence_of_scalars():
    text = """
items:
  - one
  - two
  - three
"""
    assert loads(text) == {"items": ["one", "two", "three"]}


def test_sequence_of_mappings():
    text = """
people:
  - name: Ada
    age: 36
  - name: Grace
    age: 85
"""
    assert loads(text) == {
        "people": [
            {"name": "Ada", "age": 36},
            {"name": "Grace", "age": 85},
        ]
    }


def test_sequence_of_mappings_with_nested_block():
    text = """
people:
  - name: Ada
    address:
      city: London
      zip: "12345"
  - name: Grace
    address:
      city: NYC
      zip: "67890"
"""
    result = loads(text)
    assert result["people"][0]["address"] == {"city": "London", "zip": "12345"}
    assert result["people"][1]["name"] == "Grace"
    assert result["people"][1]["address"]["city"] == "NYC"


def test_quoted_strings():
    text = "a: 'single'\nb: \"double\"\nc: plain text\n"
    assert loads(text) == {"a": "single", "b": "double", "c": "plain text"}


def test_scalars_types():
    text = """
a: true
b: false
c: null
d: ~
e:
f: 42
g: 3.14
h: "42"
"""
    result = loads(text)
    assert result["a"] is True
    assert result["b"] is False
    assert result["c"] is None
    assert result["d"] is None
    assert result["e"] is None
    assert result["f"] == 42
    assert result["g"] == 3.14
    assert result["h"] == "42"


def test_flow_sequence_and_mapping():
    text = "tags: [read, write, admin]\nobj: {a: 1, b: 2}\n"
    result = loads(text)
    assert result["tags"] == ["read", "write", "admin"]
    assert result["obj"] == {"a": 1, "b": 2}


def test_comments_and_blank_lines():
    text = """
# top comment
a: 1  # trailing comment

b: 2
"""
    assert loads(text) == {"a": 1, "b": 2}


def test_hash_inside_string_is_not_a_comment():
    text = 'a: "value # not a comment"\n'
    assert loads(text) == {"a": "value # not a comment"}


def test_literal_block_scalar():
    text = """
description: |
  line one
  line two
"""
    result = loads(text)
    assert result["description"] == "line one\nline two"


def test_folded_block_scalar():
    text = """
description: >
  line one
  line two
"""
    result = loads(text)
    assert result["description"] == "line one line two"


def test_empty_document():
    assert loads("") is None
    assert loads("\n\n") is None


def test_document_markers_ignored():
    text = "---\na: 1\n"
    assert loads(text) == {"a": 1}


def test_top_level_sequence():
    text = "- a\n- b\n- c\n"
    assert loads(text) == ["a", "b", "c"]


def test_openapi_like_document():
    text = """
openapi: "3.0.0"
info:
  title: Example API
  version: "1.0.0"
paths:
  /pets:
    get:
      operationId: listPets
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Pet'
components:
  schemas:
    Pet:
      type: object
      required:
        - id
        - name
      properties:
        id:
          type: integer
        name:
          type: string
        tag:
          type: string
"""
    result = loads(text)
    assert result["openapi"] == "3.0.0"
    assert result["info"]["title"] == "Example API"
    op = result["paths"]["/pets"]["get"]
    assert op["operationId"] == "listPets"
    assert op["parameters"][0]["name"] == "limit"
    assert op["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"] == (
        "#/components/schemas/Pet"
    )
    pet = result["components"]["schemas"]["Pet"]
    assert pet["required"] == ["id", "name"]
    assert set(pet["properties"]) == {"id", "name", "tag"}


def test_nested_sequence_shorthand():
    text = """
matrix:
  - - 1
    - 2
    - 3
  - - 4
    - 5
"""
    assert loads(text) == {"matrix": [[1, 2, 3], [4, 5]]}


def test_deeply_nested_sequence_shorthand():
    text = "grid:\n  - - - 1\n      - 2\n  - - - 3\n      - 4\n"
    assert loads(text) == {"grid": [[[1, 2]], [[3, 4]]]}


def test_sequence_mixing_nested_list_and_mapping_items():
    text = """
items:
  - - a
    - b
  - name: x
    value: 1
"""
    assert loads(text) == {"items": [["a", "b"], {"name": "x", "value": 1}]}


def test_tabs_rejected():
    with pytest.raises(YamlSubsetError):
        loads("a:\n\tb: 1\n")
