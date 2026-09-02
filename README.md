# oadiff

A dependency-free CLI that diffs two OpenAPI/Swagger specs (JSON or YAML) and
classifies every change as **breaking** or **non-breaking** for API
consumers — not just "these two files differ."

```
$ oadiff petstore_v1.yaml petstore_v2.yaml

Comparing petstore_v1.yaml -> petstore_v2.yaml

7 breaking, 3 non-breaking, 0 needs review (10 total changes)

[BREAKING    ] DELETE /pets/{petId}: DELETE /pets/{petId} was removed
[BREAKING    ] GET /pets [parameters.query:apiKey]: parameter 'apiKey' (query) added (required)
[BREAKING    ] GET /pets [responses.200.application/json.items.properties.id]: type changed from 'integer' to 'string'
[BREAKING    ] POST /pets [requestBody.application/json.properties.category]: property 'category' added (required)
...
[non-breaking] GET /pets [responses.200.application/json.items.properties.status]: enum value(s) removed: 'sold'
```

## Why

A whole-document diff (`diff old.yaml new.yaml`) tells you two specs aren't
identical. It doesn't tell you whether the difference matters — whether
adding a new optional response field is safe (it is) or removing a required
request parameter will break every existing client (it will). `oadiff`
applies the actual rules of what makes an OpenAPI change safe or unsafe for
the people calling the API, and reports only the classification consumers
actually care about.

It's the fourth member of a small family of diff-aware CI-gate tools in this
portfolio: [pr-risk-scorer](https://github.com/arnavchawla26/pr-risk-scorer)
flags a pull request as risky when it changes code without matching test
changes; [test-coverage-gap-finder](https://github.com/arnavchawla26/test-coverage-gap-finder)
tells you exactly which changed lines still have no test coverage;
[commit-lint-changelog](https://github.com/arnavchawla26/commit-lint-changelog)
keeps commit history and changelogs honest. `oadiff` closes the loop on the
API contract itself: did this change break the contract, and can CI catch it
before it ships?

## How it works

1. **Load** — parse the old and new spec files (JSON, or the practical
   subset of YAML that real OpenAPI documents use — see
   [`oadiff/yaml_subset.py`](oadiff/yaml_subset.py)).
2. **Resolve** — recursively resolve every local `$ref` (`#/components/...`)
   so two specs that organize `components` differently still compare on
   equal footing. Circular schemas are detected and treated as an opaque,
   ref-identity-compared node rather than recursing forever.
3. **Normalize** — flatten `paths` into a `(METHOD, path) -> Operation` map:
   parameters (path-level ones merged with, and overridden by, operation-level
   ones), the request body schema per content type, and the response schema
   per status code per content type.
4. **Diff** — compare the two normalized specs operation by operation,
   parameter by parameter, and recursively through each JSON Schema
   (properties, required, enum, type, format, nullable, additionalProperties,
   array items), classifying every difference using the rule table below.
5. **Report** — render as text, Markdown, or JSON, sorted breaking-first.

Because comparison happens on the *resolved, consumer-facing* shape of each
operation rather than on the raw `components/schemas` section, a schema that
was renamed, restructured, or split into new `$ref`s produces **no noise**
as long as what a client actually sends and receives didn't change — and a
schema edit is only reported against the operations that actually use it.

### The breaking-change rules

The same structural change means something different depending on which way
the data flows. `oadiff` diffs *request* schemas (what a client sends: request
bodies, parameters) and *response* schemas (what the server sends back) with
opposite defaults for "growing" vs. "shrinking" a schema:

| Change | In a request | In a response |
| --- | --- | --- |
| Field/parameter removed | non-breaking | **breaking** |
| Required field/parameter added | **breaking** | non-breaking |
| Optional field/parameter added | non-breaking | non-breaking |
| Field/parameter becomes required | **breaking** | non-breaking |
| Field/parameter becomes optional | non-breaking | **breaking** |
| `type`/`format` changed | **breaking** | **breaking** |
| Enum value removed | **breaking** | non-breaking |
| Enum value added | non-breaking | **breaking** |
| `additionalProperties` set to `false` | **breaking** | non-breaking |
| `additionalProperties` no longer `false` | non-breaking | **breaking** |
| Path or HTTP method removed | — | **breaking** |
| Path, method, or new response status added | — | non-breaking |
| Content type removed (request or response) | **breaking** | **breaking** |
| `oneOf`/`anyOf`/`allOf` added or removed | flagged for manual review (not deeply diffed in v1) | same |

The intuition in one line: a request schema is a contract on what the
*server must still accept*; a response schema is a contract on what the
*client can still rely on receiving*. Growing what a server accepts, or
shrinking what a server promises to send, is always safe to add; shrinking
what a server accepts, or growing what it promises, is where old clients
break.

## Tech stack

Python 3.9+, standard library only — `json`, `argparse`, `dataclasses`,
`enum`. No PyYAML, no `openapi-spec-validator`, nothing to `pip install` for
normal use (only `pytest` for running the test suite), matching the
zero-dependency pattern used across this portfolio's other CLI tools.

## Install / run

```bash
git clone https://github.com/arnavchawla26/openapi-breaking-change-detector
cd openapi-breaking-change-detector
pip install -e .          # installs the `oadiff` console script
oadiff old.yaml new.yaml
```

Or run it straight from the source tree without installing:

```bash
python -m oadiff.cli old.yaml new.yaml
```

### CLI flags

| Flag | Description |
| --- | --- |
| `old_spec`, `new_spec` | positional paths to the two spec files (JSON or YAML) |
| `--format`, `-f {text,markdown,json}` | output format (default `text`) |
| `--output`, `-o FILE` | write the report to a file instead of stdout |
| `--fail-on-breaking` | exit with status `1` if any breaking change was found — the flag for a CI gate |
| `--only-breaking` | drop non-breaking changes from the report, keeping only breaking and "needs review" items |
| `--version` | print the version and exit |

Example CI gate step:

```bash
oadiff api/v1.yaml api/v1-candidate.yaml --fail-on-breaking --format markdown -o breaking-changes.md
```

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

93 tests across YAML parsing, `$ref` resolution, spec normalization, schema
diffing (every rule in the table above, both directions), the top-level
operation differ, all three report renderers, and CLI end-to-end tests —
including two tests that invoke the real installed entry point
(`python -m oadiff.cli ...`) via `subprocess`, not a mocked `main()` call.

The YAML subset parser was also stress-tested by hand against GitHub's own
public OpenAPI spec (the full REST API description — 8.8 MB, ~232k lines,
845 operations, pulled from the
[APIs.guru directory](https://github.com/APIs-guru/openapi-directory)): it
parses correctly, and diffing it against itself correctly reports zero
changes. That test isn't checked in (the file is too large for this repo
and pulling it requires network access this test suite shouldn't depend on
in CI), but it's how a real nested-sequence edge case
(`- - 1302998400` — a sequence item that is itself a sequence, used in some
example payloads) was caught and fixed during development.

## Current status

Functional v1. Handles the common cases well: path/operation add-remove,
parameter add/remove/required-flip, request body add/remove/required-flip,
response status/content-type add/remove, and full recursive schema diffing
(properties, required, type, format, enum, nullable, additionalProperties,
array items) with correct request-vs-response severity in both directions.

Known limitations, honestly listed:

- **YAML support is a practical subset, not full YAML 1.1/1.2.** No anchors
  (`&`/`*`), no tags, no multi-document streams, no complex mapping keys.
  On unsupported input, `oadiff` raises a clear parse error naming the line
  number rather than silently misreading the file. In practice this covers
  real-world OpenAPI YAML very well (validated against GitHub's full public
  spec, see above) because those documents overwhelmingly stick to block
  mappings/sequences and simple scalars.
- **`oneOf`/`anyOf`/`allOf` are not deeply diffed.** A change involving them
  is flagged as "needs review" (severity `unknown`) rather than silently
  ignored or incorrectly classified, but `oadiff` won't tell you *what*
  changed inside a composed schema in v1.
- **External `$ref`s (other files or URLs) are not fetched or resolved** —
  only local (`#/...`) refs are. An external ref is left as-is, so
  properties inside it won't be diffed. This is a deliberate v1 boundary,
  not an oversight: resolving arbitrary external refs would mean giving the
  tool network/filesystem access beyond the two files it's told to compare.
- **No OpenAPI/Swagger schema validation.** `oadiff` assumes both inputs are
  structurally valid specs; a malformed spec produces a `KeyError`-shaped
  crash rather than a friendly validation report. (`--fail-on-breaking`
  wraps the diff itself in error handling, not the input's overall
  well-formedness.)
- **No CI/PR-comment integration** (e.g. a GitHub Action or bot comment) —
  the `--fail-on-breaking` exit code and Markdown output are meant to make
  wiring that up straightforward, but the wiring itself isn't built yet.
- Not published to PyPI — install from source as shown above.

## License

MIT — see [LICENSE](LICENSE).
