"""Unit tests for `scripts/detect_conformance.py`."""

import json
from pathlib import Path
from typing import Dict

from scripts import detect_conformance
from scripts.detect_conformance import ConformanceDetector


def _build_comprehensive_spec() -> Dict[str, object]:
    """Build an exhaustive OpenAPI 3.2.0 specification exercising every object and field."""
    return {
        "openapi": "3.2.0",
        "$self": "https://example.com/openapi.json",
        "jsonSchemaDialect": "https://spec.openapis.org/oas/3.1/dialect/base",
        "info": {
            "title": "Comprehensive API",
            "summary": "Short summary",
            "description": "Full description",
            "termsOfService": "https://example.com/tos",
            "version": "1.0.0",
            "contact": {
                "name": "Support",
                "url": "https://example.com/support",
                "email": "support@example.com",
            },
            "license": {
                "name": "Apache 2.0",
                "identifier": "Apache-2.0",
                "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
            },
        },
        "servers": [
            {
                "url": "https://api.example.com/{env}",
                "description": "Main server",
                "name": "prod",
                "variables": {
                    "env": {
                        "enum": ["prod", "staging"],
                        "default": "prod",
                        "description": "Environment",
                    }
                },
            }
        ],
        "paths": {
            "/pets": {
                "$ref": "#/components/pathItems/SharedPet",
                "summary": "Pets path",
                "description": "Pets path desc",
                "get": {
                    "tags": ["pet"],
                    "summary": "List pets",
                    "description": "List all pets",
                    "operationId": "listPets",
                    "deprecated": False,
                    "externalDocs": {"description": "Op docs", "url": "https://example.com/op"},
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "Max items",
                            "required": False,
                            "deprecated": False,
                            "allowEmptyValue": False,
                            "style": "form",
                            "explode": True,
                            "allowReserved": False,
                            "example": 10,
                            "schema": {"type": "integer"},
                            "examples": {
                                "ex1": {
                                    "summary": "Ex summary",
                                    "description": "Ex desc",
                                    "value": 10,
                                    "dataValue": 10,
                                    "serializedValue": "10",
                                    "externalValue": "https://example.com/ex",
                                },
                                "exRef": {"$ref": "#/components/examples/RefEx", "summary": "s", "description": "d"},
                            },
                            "content": {
                                "application/json": {
                                    "example": 10,
                                    "schema": {"type": "integer"},
                                    "itemSchema": {"type": "integer"},
                                    "examples": {"e1": {"value": 1}},
                                    "encoding": {
                                        "field1": {
                                            "contentType": "text/plain",
                                            "style": "form",
                                            "explode": True,
                                            "allowReserved": False,
                                            "headers": {
                                                "X-Rate": {
                                                    "description": "Rate",
                                                    "required": True,
                                                    "deprecated": False,
                                                    "style": "simple",
                                                    "explode": False,
                                                    "example": 100,
                                                    "schema": {"type": "integer"},
                                                    "examples": {"h1": {"value": 100}},
                                                    "content": {"text/plain": {"schema": {"type": "string"}}},
                                                },
                                                "X-Ref": {"$ref": "#/components/headers/RefH"},
                                            },
                                            "encoding": {"sub": {"contentType": "text/plain"}},
                                            "prefixEncoding": [{"contentType": "text/plain"}],
                                            "itemEncoding": {"contentType": "text/plain"},
                                        }
                                    },
                                    "prefixEncoding": [{"contentType": "text/plain"}],
                                    "itemEncoding": {"contentType": "text/plain"},
                                }
                            },
                        },
                        {"$ref": "#/components/parameters/RefParam"},
                    ],
                    "requestBody": {
                        "description": "Body",
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {
                        "default": {
                            "summary": "Default err",
                            "description": "Error",
                            "headers": {"X-Err": {"description": "err header"}},
                            "content": {"application/json": {"schema": {"type": "object"}}},
                            "links": {
                                "NextLink": {
                                    "operationRef": "#/paths/~1pets/get",
                                    "operationId": "listPets",
                                    "parameters": {"limit": 10},
                                    "requestBody": {},
                                    "description": "Next page",
                                    "server": {"url": "https://api.example.com"},
                                },
                                "RefLink": {"$ref": "#/components/links/RefL"},
                            },
                        },
                        "200": {"$ref": "#/components/responses/RefResp"},
                    },
                    "callbacks": {
                        "onEvent": {
                            "{$request.query.callbackUrl}": {
                                "post": {"summary": "Callback post", "responses": {"200": {"description": "ok"}}}
                            }
                        },
                        "refCb": {"$ref": "#/components/callbacks/RefCb"},
                    },
                    "security": [{"api_key": []}],
                    "servers": [{"url": "https://op.example.com"}],
                },
                "query": {"summary": "Query pets"},
                "additionalOperations": {"PURGE": {"summary": "Purge pets"}},
                "servers": [{"url": "https://path.example.com"}],
                "parameters": [{"name": "p1", "in": "header"}],
            }
        },
        "webhooks": {"newPet": {"post": {"summary": "New pet webhook"}}},
        "components": {
            "schemas": {
                "BoolSchema": True,
                "RefSchema": {"$ref": "#/components/schemas/Pet", "summary": "ref sum", "description": "ref desc"},
                "Pet": {
                    "type": "object",
                    "discriminator": {
                        "propertyName": "petType",
                        "mapping": {"dog": "#/components/schemas/Dog"},
                        "defaultMapping": "#/components/schemas/Pet",
                    },
                    "xml": {
                        "name": "Pet",
                        "namespace": "https://example.com/schema",
                        "prefix": "p",
                        "attribute": False,
                        "wrapped": False,
                        "nodeType": "element",
                    },
                    "externalDocs": {"description": "Schema docs", "url": "https://example.com/s"},
                    "example": {"name": "Rex"},
                    "properties": {"id": {"type": "integer"}},
                    "items": {"type": "string"},
                    "allOf": [{"type": "object"}],
                    "anyOf": [{"type": "object"}],
                    "oneOf": [{"type": "object"}],
                    "not": {"type": "null"},
                    "additionalProperties": {"type": "string"},
                },
            },
            "responses": {"RefResp": {"description": "resp"}},
            "parameters": {"RefParam": {"name": "rp", "in": "query"}},
            "examples": {"RefEx": {"value": "x"}},
            "requestBodies": {
                "RefBody": {"$ref": "#/components/requestBodies/Other"},
                "RealBody": {"description": "rb"},
            },
            "headers": {"RefH": {"description": "rh"}},
            "securitySchemes": {
                "RefSec": {"$ref": "#/components/securitySchemes/OAuth"},
                "OAuth": {
                    "type": "oauth2",
                    "description": "OAuth2 sec",
                    "name": "Authorization",
                    "in": "header",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "openIdConnectUrl": "https://example.com/oidc",
                    "oauth2MetadataUrl": "https://example.com/meta",
                    "deprecated": False,
                    "flows": {
                        "implicit": {
                            "authorizationUrl": "https://example.com/auth",
                            "deviceAuthorizationUrl": "https://example.com/dev",
                            "tokenUrl": "https://example.com/token",
                            "refreshUrl": "https://example.com/refresh",
                            "scopes": {"read": "Read access"},
                        },
                        "password": {"tokenUrl": "https://example.com/token", "scopes": {}},
                        "clientCredentials": {"tokenUrl": "https://example.com/token", "scopes": {}},
                        "authorizationCode": {
                            "authorizationUrl": "https://example.com/auth",
                            "tokenUrl": "https://example.com/token",
                            "scopes": {},
                        },
                        "deviceAuthorization": {
                            "deviceAuthorizationUrl": "https://example.com/dev",
                            "tokenUrl": "https://example.com/token",
                            "scopes": {},
                        },
                    },
                },
            },
            "links": {"RefL": {"operationId": "listPets"}},
            "callbacks": {"RefCb": {"{$url}": {"get": {"summary": "cb"}}}},
            "pathItems": {"SharedPet": {"summary": "shared"}},
            "mediaTypes": {"JsonMedia": {"example": 1}},
        },
        "security": [{"api_key": []}],
        "tags": [
            {
                "name": "pet",
                "summary": "Pets tag",
                "description": "Everything about your Pets",
                "parent": "animal",
                "kind": "nav",
                "externalDocs": {"description": "Tag docs", "url": "https://example.com/t"},
            }
        ],
        "externalDocs": {"description": "Root docs", "url": "https://example.com"},
    }


def test_detector_full_spec_and_markdown_update(tmp_path: Path) -> None:
    """Verify `ConformanceDetector` walks all objects/properties and updates markdown tables."""
    spec = _build_comprehensive_spec()
    in_path = tmp_path / "in.json"
    out_path = tmp_path / "out.yaml"
    in_path.write_text(json.dumps(spec), encoding="utf-8")
    out_path.write_text(json.dumps(spec), encoding="utf-8")

    features = detect_conformance.detect_features(in_path, out_path)
    assert "OpenAPI Object" in features
    assert "Info Object::title" in features
    assert "Discriminator Object" in features
    assert "XML Object::nodeType" in features
    assert "Security Requirement Object" in features
    assert "OAuth Flows Object::deviceAuthorization" in features
    assert "Tag Object::kind" in features

    assert detect_conformance.main([str(in_path), str(out_path)]) == 0

    missing_md = tmp_path / "missing.md"
    assert detect_conformance.main([str(in_path), str(out_path), "--markdown", str(missing_md)]) == 1

    md_file = tmp_path / "client-sdk.md"
    nl = chr(10)
    md_content = nl.join(
        [
            "# Conformance",
            "### `OpenAPI Object`",
            "| Property | Type | Status / Notes |",
            "| :--- | :--- | :--- |",
            "| `(Object Node)` | Object | [ ] |",
            "| `openapi` | string | [ ] |",
            "| `jsonSchemaDialect` | string | [x] |",
            "### Security Requirement Object",
            "| Property | Type | Status / Notes |",
            "| :--- | :--- | :--- |",
            "| `(Implicit / Array of Map)` | array | [ ] |",
            "| `unmatchedProp` | string | [ ] |",
            "### `Schema Object`",
            "| Property | Type | Status / Notes |",
            "| :--- | :--- | :--- |",
            "| `(Any property)` | any | [ ] |",
            "| short |",
            "### Other Section",
            "| ignored |",
        ]
    )
    md_file.write_text(md_content, encoding="utf-8")
    assert detect_conformance.main([str(in_path), str(out_path), "--markdown", str(md_file)]) == 0
    updated = md_file.read_text(encoding="utf-8")
    assert "[x]" in updated

    features_no_sec = features - {"OpenAPI Object", "Security Requirement Object", "Schema Object"}
    md_file.write_text(md_content, encoding="utf-8")
    detect_conformance.update_markdown_matrix(md_file, features_no_sec)


def test_detector_edge_cases_and_non_dict_guards(tmp_path: Path) -> None:
    """Verify all guard clauses, value mismatch branches, and fallback paths in `ConformanceDetector`."""
    det = ConformanceDetector()

    assert det._values_match(1, 1.0) is True
    assert det._values_match(True, 1) is False
    assert det._values_match("a", 1) is False
    assert det._values_match({"a": 1}, {}) is False
    assert det._values_match([1], [1, 2]) is False

    assert det._check_ref("not-a-dict", {}) is False
    assert det._check_ref({"$ref": "#/a"}, "not-a-dict") is True
    assert det._check_ref({"$ref": "#/a"}, {"$ref": "#/b"}) is True

    det.walk_list("not-a-list", [], det.walk_tag)
    det.walk_list(["not-a-dict", {"other": 1}], ["not-a-dict", {"other": 1}], det.walk_tag)
    det.walk_list([{"name": "missing"}, {"other": 2}], ["not-a-dict"], det.walk_tag)

    det.walk_dict("not-a-dict", {}, det.walk_tag)

    for fn in (
        det.walk_contact,
        det.walk_license,
        det.walk_info,
        det.walk_server_var,
        det.walk_server,
        det.walk_external_docs,
        det.walk_schema,
        det.walk_example,
        det.walk_header,
        det.walk_encoding,
        det.walk_media_type,
        det.walk_parameter,
        det.walk_request_body,
        det.walk_link,
        det.walk_response,
        det.walk_responses,
        det.walk_callback,
        det.walk_operation,
        det.walk_path_item,
        det.walk_paths,
        det.walk_oauth_flow,
        det.walk_oauth_flows,
        det.walk_security_scheme,
        det.walk_components,
        det.walk_tag,
        det.walk_openapi_doc,
    ):
        fn("not-a-dict", "not-a-dict")
        fn({"a": 1}, {"a": 2})

    det.walk_schema(
        {
            "discriminator": {"propertyName": "x"},
            "xml": {"name": "x"},
            "properties": {"p": {"type": "string"}},
            "items": {"type": "string"},
            "additionalProperties": {"type": "string"},
        },
        {
            "discriminator": "not-dict",
            "xml": "not-dict",
            "properties": "not-dict",
            "items": "not-dict",
            "additionalProperties": "not-dict",
        },
    )
    det.walk_schema(
        {
            "discriminator": {"propertyName": "a"},
            "xml": {"name": "a"},
            "properties": {"missing_prop": {"type": "string"}},
        },
        {
            "discriminator": {"propertyName": "b"},
            "xml": {"name": "b"},
            "properties": {},
        },
    )
    det.walk_schema(True, True)
    det.walk_schema(True, False)
    det.walk_schema({"a": 1}, {})
    det.walk_schema({}, {"type": "object"})

    det.walk_responses({"x-ext": {}, "404": {}}, {"200": {}})
    det.walk_callback({"x-ext": {}, "{cb}": {}}, {})
    det.walk_paths({"x-ext": {}, "/missing": {}}, {})

    det.walk_operation({"security": [{"a": []}]}, {"security": "invalid"})
    det.walk_openapi_doc({"security": [{"a": []}]}, {"security": "invalid"})

    yaml_file = tmp_path / "doc.yaml"
    yaml_file.write_text("openapi: 3.2.0", encoding="utf-8")
    assert detect_conformance.load_doc(yaml_file) == {"openapi": "3.2.0"}

    list_file = tmp_path / "list.json"
    list_file.write_text("[1, 2]", encoding="utf-8")
    assert detect_conformance.load_doc(list_file) == {}
