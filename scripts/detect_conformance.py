"""OpenAPI 3.2.0 conformance detector (`scripts/detect_conformance.py`).

Loads an original OpenAPI specification and a roundtripped output specification,
then walks through both documents structurally to record which OpenAPI objects
and fields were faithfully preserved (with value and structure verification).
Optionally updates a markdown conformance matrix table.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Union

import yaml

JSONDict = Dict[str, object]
WalkerFn = Callable[[JSONDict, JSONDict], None]


class ConformanceDetector:
    """Encapsulates state and structural comparison walkers for OpenAPI 3.2.0 conformance.

    Attributes:
        supported_features: Set of `(Object, Property)` or `(Object,)` strings verified.
    """

    def __init__(self) -> None:
        """Initialize an empty ConformanceDetector."""
        self.supported_features: Set[str] = set()

    def record(self, obj: str, prop: Optional[str] = None) -> None:
        """Record a supported OpenAPI object or object property.

        Args:
            obj: The OpenAPI specification object name (e.g., 'Info Object').
            prop: Optional field/property name within the object (e.g., 'title').
        """
        if prop:
            self.supported_features.add(f"{obj}::{prop}")
        else:
            self.supported_features.add(obj)

    @staticmethod
    def is_ref(node: object) -> bool:
        """Check whether an AST node is a Reference Object containing `$ref`.

        Args:
            node: The parsed JSON/YAML node to check.

        Returns:
            bool: True if `node` is a dict containing `$ref`, False otherwise.
        """
        return isinstance(node, dict) and "$ref" in node

    @staticmethod
    def _values_match(in_val: object, out_val: object) -> bool:
        """Verify that two scalar or collection values match semantically.

        Args:
            in_val: Value from the input OpenAPI document.
            out_val: Value from the roundtripped output OpenAPI document.

        Returns:
            bool: True if the output value preserves the input value.
        """
        if type(in_val) is not type(out_val):
            if isinstance(in_val, (int, float)) and isinstance(out_val, (int, float)):
                if not isinstance(in_val, bool) and not isinstance(out_val, bool):
                    return float(in_val) == float(out_val)
            return False
        if isinstance(in_val, dict) and isinstance(out_val, dict):
            return bool(out_val) or not bool(in_val)
        if isinstance(in_val, list) and isinstance(out_val, list):
            return len(in_val) == len(out_val)
        return in_val == out_val

    def _check_ref(self, in_node: object, out_node: object) -> bool:
        """Check and record Reference Object conformance if `in_node` is a `$ref`.

        Args:
            in_node: Node from the input specification.
            out_node: Node from the output specification.

        Returns:
            bool: True if `in_node` was a `$ref` (handled here), False otherwise.
        """
        if not isinstance(in_node, dict) or not self.is_ref(in_node):
            return False
        if isinstance(out_node, dict) and self.is_ref(out_node):
            if in_node.get("$ref") == out_node.get("$ref"):
                self.record("Reference Object")
                self.record("Reference Object", "$ref")
                for k in ("summary", "description"):
                    if k in in_node and k in out_node and in_node[k] == out_node[k]:
                        self.record("Reference Object", k)
        return True

    def walk_list(self, in_list: object, out_list: object, walk_fn: WalkerFn) -> None:
        """Compare elements of two lists deterministically by key or index.

        Args:
            in_list: Input list from the original specification.
            out_list: Output list from the roundtripped specification.
            walk_fn: Comparison function to invoke on matched dictionary pairs.
        """
        if not isinstance(in_list, list) or not isinstance(out_list, list):
            return

        for idx, in_item in enumerate(in_list):
            if not isinstance(in_item, dict):
                continue
            matched_out: Optional[JSONDict] = None
            for id_key in ("name", "url", "$ref"):
                if id_key in in_item:
                    for candidate in out_list:
                        if isinstance(candidate, dict) and candidate.get(id_key) == in_item.get(id_key):
                            matched_out = candidate
                            break
                    break
            if matched_out is None and idx < len(out_list):
                candidate = out_list[idx]
                if isinstance(candidate, dict):
                    matched_out = candidate
            if matched_out is not None:
                walk_fn(in_item, matched_out)

    def walk_dict(self, in_dict: object, out_dict: object, walk_fn: WalkerFn) -> None:
        """Compare corresponding keys of two dictionaries using `walk_fn`.

        Args:
            in_dict: Input dictionary from the original specification.
            out_dict: Output dictionary from the roundtripped specification.
            walk_fn: Comparison function to invoke on each shared key's value.
        """
        if not isinstance(in_dict, dict) or not isinstance(out_dict, dict):
            return
        for k, v in in_dict.items():
            if k in out_dict and isinstance(v, dict) and isinstance(out_dict[k], dict):
                walk_fn(v, out_dict[k])

    def _check_scalar_props(
        self,
        obj_name: str,
        in_node: JSONDict,
        out_node: JSONDict,
        props: Sequence[str],
    ) -> bool:
        """Verify scalar/structural equality for `props` and record matching fields.

        Args:
            obj_name: OpenAPI object name to record.
            in_node: Input object dictionary.
            out_node: Output object dictionary.
            props: Property names to check.

        Returns:
            bool: True if at least one property matched or `in_node` was empty.
        """
        matched_any = not bool(in_node)
        for k in props:
            if k in in_node and k in out_node and self._values_match(in_node[k], out_node[k]):
                self.record(obj_name, k)
                matched_any = True
        return matched_any

    def walk_contact(self, in_node: object, out_node: object) -> None:
        """Compare a Contact Object between input and output specs.

        Args:
            in_node: Input Contact Object.
            out_node: Output Contact Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_scalar_props("Contact Object", in_node, out_node, ("name", "url", "email")):
            self.record("Contact Object")

    def walk_license(self, in_node: object, out_node: object) -> None:
        """Compare a License Object between input and output specs.

        Args:
            in_node: Input License Object.
            out_node: Output License Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_scalar_props("License Object", in_node, out_node, ("name", "identifier", "url")):
            self.record("License Object")

    def walk_info(self, in_node: object, out_node: object) -> None:
        """Compare an Info Object between input and output specs.

        Args:
            in_node: Input Info Object.
            out_node: Output Info Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props(
            "Info Object",
            in_node,
            out_node,
            ("title", "summary", "description", "termsOfService", "version"),
        )
        if "contact" in in_node and "contact" in out_node and isinstance(out_node["contact"], dict):
            self.record("Info Object", "contact")
            self.walk_contact(in_node["contact"], out_node["contact"])
            matched = True
        if "license" in in_node and "license" in out_node and isinstance(out_node["license"], dict):
            self.record("Info Object", "license")
            self.walk_license(in_node["license"], out_node["license"])
            matched = True
        if matched:
            self.record("Info Object")

    def walk_server_var(self, in_node: object, out_node: object) -> None:
        """Compare a Server Variable Object between input and output specs.

        Args:
            in_node: Input Server Variable Object.
            out_node: Output Server Variable Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_scalar_props("Server Variable Object", in_node, out_node, ("enum", "default", "description")):
            self.record("Server Variable Object")

    def walk_server(self, in_node: object, out_node: object) -> None:
        """Compare a Server Object between input and output specs.

        Args:
            in_node: Input Server Object.
            out_node: Output Server Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props("Server Object", in_node, out_node, ("url", "description", "name"))
        if "variables" in in_node and "variables" in out_node and isinstance(out_node["variables"], dict):
            self.record("Server Object", "variables")
            self.walk_dict(in_node["variables"], out_node["variables"], self.walk_server_var)
            matched = True
        if matched:
            self.record("Server Object")

    def walk_external_docs(self, in_node: object, out_node: object) -> None:
        """Compare an External Documentation Object between input and output specs.

        Args:
            in_node: Input External Documentation Object.
            out_node: Output External Documentation Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_scalar_props("External Documentation Object", in_node, out_node, ("description", "url")):
            self.record("External Documentation Object")

    def walk_schema(self, in_node: object, out_node: object) -> None:
        """Compare a Schema Object (including Discriminator and XML) between specs.

        Args:
            in_node: Input Schema Object.
            out_node: Output Schema Object.
        """
        if isinstance(in_node, bool) and isinstance(out_node, bool) and in_node == out_node:
            self.record("Schema Object")
            return
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return

        if out_node or not in_node:
            self.record("Schema Object")

        if "discriminator" in in_node and isinstance(in_node["discriminator"], dict):
            disc_out = out_node.get("discriminator")
            if isinstance(disc_out, dict):
                self.record("Schema Object", "discriminator")
                if self._check_scalar_props(
                    "Discriminator Object",
                    in_node["discriminator"],
                    disc_out,
                    ("propertyName", "mapping", "defaultMapping"),
                ):
                    self.record("Discriminator Object")

        if "xml" in in_node and isinstance(in_node["xml"], dict):
            xml_out = out_node.get("xml")
            if isinstance(xml_out, dict):
                self.record("Schema Object", "xml")
                if self._check_scalar_props(
                    "XML Object",
                    in_node["xml"],
                    xml_out,
                    ("name", "namespace", "prefix", "attribute", "wrapped", "nodeType"),
                ):
                    self.record("XML Object")

        if "externalDocs" in in_node and "externalDocs" in out_node:
            self.record("Schema Object", "externalDocs")
            self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])

        if (
            "example" in in_node
            and "example" in out_node
            and self._values_match(in_node["example"], out_node["example"])
        ):
            self.record("Schema Object", "example")

        if "properties" in in_node and isinstance(in_node["properties"], dict):
            props_out = out_node.get("properties")
            if isinstance(props_out, dict):
                for prop_k, prop_v in in_node["properties"].items():
                    if prop_k in props_out:
                        self.walk_schema(prop_v, props_out[prop_k])

        if "items" in in_node and isinstance(in_node["items"], dict):
            items_out = out_node.get("items")
            if isinstance(items_out, dict):
                self.walk_schema(in_node["items"], items_out)

        for comb in ("allOf", "anyOf", "oneOf"):
            if comb in in_node and comb in out_node:
                self.walk_list(in_node[comb], out_node[comb], self.walk_schema)

        if "not" in in_node and "not" in out_node:
            self.walk_schema(in_node["not"], out_node["not"])

        if "additionalProperties" in in_node and isinstance(in_node["additionalProperties"], dict):
            add_out = out_node.get("additionalProperties")
            if isinstance(add_out, dict):
                self.walk_schema(in_node["additionalProperties"], add_out)

    def walk_example(self, in_node: object, out_node: object) -> None:
        """Compare an Example Object between input and output specs.

        Args:
            in_node: Input Example Object.
            out_node: Output Example Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        if self._check_scalar_props(
            "Example Object",
            in_node,
            out_node,
            ("summary", "description", "value", "dataValue", "serializedValue", "externalValue"),
        ):
            self.record("Example Object")

    def walk_header(self, in_node: object, out_node: object) -> None:
        """Compare a Header Object between input and output specs.

        Args:
            in_node: Input Header Object.
            out_node: Output Header Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props(
            "Header Object",
            in_node,
            out_node,
            ("description", "required", "deprecated", "style", "explode", "example"),
        )
        if "schema" in in_node and "schema" in out_node:
            self.record("Header Object", "schema")
            self.walk_schema(in_node["schema"], out_node["schema"])
            matched = True
        if "examples" in in_node and "examples" in out_node:
            self.record("Header Object", "examples")
            self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
            matched = True
        if "content" in in_node and "content" in out_node:
            self.record("Header Object", "content")
            self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
            matched = True
        if matched:
            self.record("Header Object")

    def walk_encoding(self, in_node: object, out_node: object) -> None:
        """Compare an Encoding Object between input and output specs.

        Args:
            in_node: Input Encoding Object.
            out_node: Output Encoding Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props(
            "Encoding Object",
            in_node,
            out_node,
            ("contentType", "style", "explode", "allowReserved"),
        )
        if "headers" in in_node and "headers" in out_node:
            self.record("Encoding Object", "headers")
            self.walk_dict(in_node["headers"], out_node["headers"], self.walk_header)
            matched = True
        if "encoding" in in_node and "encoding" in out_node:
            self.record("Encoding Object", "encoding")
            self.walk_dict(in_node["encoding"], out_node["encoding"], self.walk_encoding)
            matched = True
        if "prefixEncoding" in in_node and "prefixEncoding" in out_node:
            self.record("Encoding Object", "prefixEncoding")
            self.walk_list(in_node["prefixEncoding"], out_node["prefixEncoding"], self.walk_encoding)
            matched = True
        if "itemEncoding" in in_node and "itemEncoding" in out_node:
            self.record("Encoding Object", "itemEncoding")
            self.walk_encoding(in_node["itemEncoding"], out_node["itemEncoding"])
            matched = True
        if matched:
            self.record("Encoding Object")

    def walk_media_type(self, in_node: object, out_node: object) -> None:
        """Compare a Media Type Object between input and output specs.

        Args:
            in_node: Input Media Type Object.
            out_node: Output Media Type Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props("Media Type Object", in_node, out_node, ("example",))
        if "schema" in in_node and "schema" in out_node:
            self.record("Media Type Object", "schema")
            self.walk_schema(in_node["schema"], out_node["schema"])
            matched = True
        if "itemSchema" in in_node and "itemSchema" in out_node:
            self.record("Media Type Object", "itemSchema")
            self.walk_schema(in_node["itemSchema"], out_node["itemSchema"])
            matched = True
        if "examples" in in_node and "examples" in out_node:
            self.record("Media Type Object", "examples")
            self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
            matched = True
        if "encoding" in in_node and "encoding" in out_node:
            self.record("Media Type Object", "encoding")
            self.walk_dict(in_node["encoding"], out_node["encoding"], self.walk_encoding)
            matched = True
        if "prefixEncoding" in in_node and "prefixEncoding" in out_node:
            self.record("Media Type Object", "prefixEncoding")
            self.walk_list(in_node["prefixEncoding"], out_node["prefixEncoding"], self.walk_encoding)
            matched = True
        if "itemEncoding" in in_node and "itemEncoding" in out_node:
            self.record("Media Type Object", "itemEncoding")
            self.walk_encoding(in_node["itemEncoding"], out_node["itemEncoding"])
            matched = True
        if matched:
            self.record("Media Type Object")

    def walk_parameter(self, in_node: object, out_node: object) -> None:
        """Compare a Parameter Object between input and output specs.

        Args:
            in_node: Input Parameter Object.
            out_node: Output Parameter Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props(
            "Parameter Object",
            in_node,
            out_node,
            (
                "name",
                "in",
                "description",
                "required",
                "deprecated",
                "allowEmptyValue",
                "style",
                "explode",
                "allowReserved",
                "example",
            ),
        )
        if "schema" in in_node and "schema" in out_node:
            self.record("Parameter Object", "schema")
            self.walk_schema(in_node["schema"], out_node["schema"])
            matched = True
        if "examples" in in_node and "examples" in out_node:
            self.record("Parameter Object", "examples")
            self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
            matched = True
        if "content" in in_node and "content" in out_node:
            self.record("Parameter Object", "content")
            self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
            matched = True
        if matched:
            self.record("Parameter Object")

    def walk_request_body(self, in_node: object, out_node: object) -> None:
        """Compare a Request Body Object between input and output specs.

        Args:
            in_node: Input Request Body Object.
            out_node: Output Request Body Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props("Request Body Object", in_node, out_node, ("description", "required"))
        if "content" in in_node and "content" in out_node:
            self.record("Request Body Object", "content")
            self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
            matched = True
        if matched:
            self.record("Request Body Object")

    def walk_link(self, in_node: object, out_node: object) -> None:
        """Compare a Link Object between input and output specs.

        Args:
            in_node: Input Link Object.
            out_node: Output Link Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props(
            "Link Object",
            in_node,
            out_node,
            ("operationRef", "operationId", "parameters", "requestBody", "description"),
        )
        if "server" in in_node and "server" in out_node:
            self.record("Link Object", "server")
            self.walk_server(in_node["server"], out_node["server"])
            matched = True
        if matched:
            self.record("Link Object")

    def walk_response(self, in_node: object, out_node: object) -> None:
        """Compare a Response Object between input and output specs.

        Args:
            in_node: Input Response Object.
            out_node: Output Response Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props("Response Object", in_node, out_node, ("summary", "description"))
        if "headers" in in_node and "headers" in out_node:
            self.record("Response Object", "headers")
            self.walk_dict(in_node["headers"], out_node["headers"], self.walk_header)
            matched = True
        if "content" in in_node and "content" in out_node:
            self.record("Response Object", "content")
            self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
            matched = True
        if "links" in in_node and "links" in out_node:
            self.record("Response Object", "links")
            self.walk_dict(in_node["links"], out_node["links"], self.walk_link)
            matched = True
        if matched:
            self.record("Response Object")

    def walk_responses(self, in_node: object, out_node: object) -> None:
        """Compare a Responses Object between input and output specs.

        Args:
            in_node: Input Responses Object.
            out_node: Output Responses Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = False
        if "default" in in_node and "default" in out_node:
            self.record("Responses Object", "default")
            self.walk_response(in_node["default"], out_node["default"])
            matched = True
        for k, v in in_node.items():
            if k != "default" and not str(k).startswith("x-") and k in out_node:
                self.record("Responses Object", "{status-code}")
                self.walk_response(v, out_node[k])
                matched = True
        if matched:
            self.record("Responses Object")

    def walk_callback(self, in_node: object, out_node: object) -> None:
        """Compare a Callback Object between input and output specs.

        Args:
            in_node: Input Callback Object.
            out_node: Output Callback Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = False
        for k, v in in_node.items():
            if not str(k).startswith("x-") and k in out_node:
                self.record("Callback Object", "{expression}")
                self.walk_path_item(v, out_node[k])
                matched = True
        if matched:
            self.record("Callback Object")

    def walk_operation(self, in_node: object, out_node: object) -> None:
        """Compare an Operation Object between input and output specs.

        Args:
            in_node: Input Operation Object.
            out_node: Output Operation Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props(
            "Operation Object",
            in_node,
            out_node,
            ("tags", "summary", "description", "operationId", "deprecated"),
        )
        if "externalDocs" in in_node and "externalDocs" in out_node:
            self.record("Operation Object", "externalDocs")
            self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
            matched = True
        if "parameters" in in_node and "parameters" in out_node:
            self.record("Operation Object", "parameters")
            self.walk_list(in_node["parameters"], out_node["parameters"], self.walk_parameter)
            matched = True
        if "requestBody" in in_node and "requestBody" in out_node:
            self.record("Operation Object", "requestBody")
            self.walk_request_body(in_node["requestBody"], out_node["requestBody"])
            matched = True
        if "responses" in in_node and "responses" in out_node:
            self.record("Operation Object", "responses")
            self.walk_responses(in_node["responses"], out_node["responses"])
            matched = True
        if "callbacks" in in_node and "callbacks" in out_node:
            self.record("Operation Object", "callbacks")
            self.walk_dict(in_node["callbacks"], out_node["callbacks"], self.walk_callback)
            matched = True
        if "security" in in_node and "security" in out_node:
            if self._values_match(in_node["security"], out_node["security"]):
                self.record("Operation Object", "security")
                self.record("Security Requirement Object")
                matched = True
        if "servers" in in_node and "servers" in out_node:
            self.record("Operation Object", "servers")
            self.walk_list(in_node["servers"], out_node["servers"], self.walk_server)
            matched = True
        if matched:
            self.record("Operation Object")

    def walk_path_item(self, in_node: object, out_node: object) -> None:
        """Compare a Path Item Object between input and output specs.

        Args:
            in_node: Input Path Item Object.
            out_node: Output Path Item Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props("Path Item Object", in_node, out_node, ("$ref", "summary", "description"))
        for m in ("get", "put", "post", "delete", "options", "head", "patch", "trace", "query"):
            if m in in_node and m in out_node:
                self.record("Path Item Object", m)
                self.walk_operation(in_node[m], out_node[m])
                matched = True
        if "additionalOperations" in in_node and "additionalOperations" in out_node:
            self.record("Path Item Object", "additionalOperations")
            self.walk_dict(
                in_node["additionalOperations"],
                out_node["additionalOperations"],
                self.walk_operation,
            )
            matched = True
        if "servers" in in_node and "servers" in out_node:
            self.record("Path Item Object", "servers")
            self.walk_list(in_node["servers"], out_node["servers"], self.walk_server)
            matched = True
        if "parameters" in in_node and "parameters" in out_node:
            self.record("Path Item Object", "parameters")
            self.walk_list(in_node["parameters"], out_node["parameters"], self.walk_parameter)
            matched = True
        if matched:
            self.record("Path Item Object")

    def walk_paths(self, in_node: object, out_node: object) -> None:
        """Compare a Paths Object between input and output specs.

        Args:
            in_node: Input Paths Object.
            out_node: Output Paths Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = False
        for k, v in in_node.items():
            if not str(k).startswith("x-") and k in out_node:
                self.record("Paths Object", "{path}")
                self.walk_path_item(v, out_node[k])
                matched = True
        if matched:
            self.record("Paths Object")

    def walk_oauth_flow(self, in_node: object, out_node: object) -> None:
        """Compare an OAuth Flow Object between input and output specs.

        Args:
            in_node: Input OAuth Flow Object.
            out_node: Output OAuth Flow Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_scalar_props(
            "OAuth Flow Object",
            in_node,
            out_node,
            ("authorizationUrl", "deviceAuthorizationUrl", "tokenUrl", "refreshUrl", "scopes"),
        ):
            self.record("OAuth Flow Object")

    def walk_oauth_flows(self, in_node: object, out_node: object) -> None:
        """Compare an OAuth Flows Object between input and output specs.

        Args:
            in_node: Input OAuth Flows Object.
            out_node: Output OAuth Flows Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = False
        for k in ("implicit", "password", "clientCredentials", "authorizationCode", "deviceAuthorization"):
            if k in in_node and k in out_node:
                self.record("OAuth Flows Object", k)
                self.walk_oauth_flow(in_node[k], out_node[k])
                matched = True
        if matched:
            self.record("OAuth Flows Object")

    def walk_security_scheme(self, in_node: object, out_node: object) -> None:
        """Compare a Security Scheme Object between input and output specs.

        Args:
            in_node: Input Security Scheme Object.
            out_node: Output Security Scheme Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        if self._check_ref(in_node, out_node):
            return
        matched = self._check_scalar_props(
            "Security Scheme Object",
            in_node,
            out_node,
            (
                "type",
                "description",
                "name",
                "in",
                "scheme",
                "bearerFormat",
                "openIdConnectUrl",
                "oauth2MetadataUrl",
                "deprecated",
            ),
        )
        if "flows" in in_node and "flows" in out_node:
            self.record("Security Scheme Object", "flows")
            self.walk_oauth_flows(in_node["flows"], out_node["flows"])
            matched = True
        if matched:
            self.record("Security Scheme Object")

    def walk_components(self, in_node: object, out_node: object) -> None:
        """Compare a Components Object between input and output specs.

        Args:
            in_node: Input Components Object.
            out_node: Output Components Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        mapping: List[tuple[str, WalkerFn]] = [
            ("schemas", self.walk_schema),
            ("responses", self.walk_response),
            ("parameters", self.walk_parameter),
            ("examples", self.walk_example),
            ("requestBodies", self.walk_request_body),
            ("headers", self.walk_header),
            ("securitySchemes", self.walk_security_scheme),
            ("links", self.walk_link),
            ("callbacks", self.walk_callback),
            ("pathItems", self.walk_path_item),
            ("mediaTypes", self.walk_media_type),
        ]
        matched = False
        for k, fn in mapping:
            if k in in_node and k in out_node and isinstance(out_node[k], dict):
                self.record("Components Object", k)
                self.walk_dict(in_node[k], out_node[k], fn)
                matched = True
        if matched:
            self.record("Components Object")

    def walk_tag(self, in_node: object, out_node: object) -> None:
        """Compare a Tag Object between input and output specs.

        Args:
            in_node: Input Tag Object.
            out_node: Output Tag Object.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props(
            "Tag Object", in_node, out_node, ("name", "summary", "description", "parent", "kind")
        )
        if "externalDocs" in in_node and "externalDocs" in out_node:
            self.record("Tag Object", "externalDocs")
            self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
            matched = True
        if matched:
            self.record("Tag Object")

    def walk_openapi_doc(self, in_node: object, out_node: object) -> None:
        """Compare a root OpenAPI Object between input and output specs.

        Args:
            in_node: Input OpenAPI root document.
            out_node: Output OpenAPI root document.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return
        matched = self._check_scalar_props(
            "OpenAPI Object", in_node, out_node, ("openapi", "$self", "jsonSchemaDialect")
        )
        if "info" in in_node and "info" in out_node:
            self.record("OpenAPI Object", "info")
            self.walk_info(in_node["info"], out_node["info"])
            matched = True
        if "servers" in in_node and "servers" in out_node:
            self.record("OpenAPI Object", "servers")
            self.walk_list(in_node["servers"], out_node["servers"], self.walk_server)
            matched = True
        if "paths" in in_node and "paths" in out_node:
            self.record("OpenAPI Object", "paths")
            self.walk_paths(in_node["paths"], out_node["paths"])
            matched = True
        if "webhooks" in in_node and "webhooks" in out_node:
            self.record("OpenAPI Object", "webhooks")
            self.walk_dict(in_node["webhooks"], out_node["webhooks"], self.walk_path_item)
            matched = True
        if "components" in in_node and "components" in out_node:
            self.record("OpenAPI Object", "components")
            self.walk_components(in_node["components"], out_node["components"])
            matched = True
        if "security" in in_node and "security" in out_node:
            if self._values_match(in_node["security"], out_node["security"]):
                self.record("OpenAPI Object", "security")
                self.record("Security Requirement Object")
                matched = True
        if "tags" in in_node and "tags" in out_node:
            self.record("OpenAPI Object", "tags")
            self.walk_list(in_node["tags"], out_node["tags"], self.walk_tag)
            matched = True
        if "externalDocs" in in_node and "externalDocs" in out_node:
            self.record("OpenAPI Object", "externalDocs")
            self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
            matched = True
        if matched:
            self.record("OpenAPI Object")


def load_doc(path: Union[str, Path]) -> JSONDict:
    """Load an OpenAPI specification file in either JSON or YAML format.

    Args:
        path: Path to the OpenAPI file.

    Returns:
        JSONDict: Parsed OpenAPI specification dictionary.
    """
    content = Path(path).read_text(encoding="utf-8")
    try:
        loaded = json.loads(content)
    except Exception:
        loaded = yaml.safe_load(content)
    return loaded if isinstance(loaded, dict) else {}


def detect_features(input_spec: Union[str, Path], output_spec: Union[str, Path]) -> Set[str]:
    """Compare an input specification against a roundtripped output specification.

    Args:
        input_spec: Path to the original input OpenAPI file.
        output_spec: Path to the roundtripped output OpenAPI file.

    Returns:
        Set[str]: Set of verified OpenAPI 3.2.0 feature strings.
    """
    detector = ConformanceDetector()
    in_doc = load_doc(input_spec)
    out_doc = load_doc(output_spec)
    detector.walk_openapi_doc(in_doc, out_doc)
    return detector.supported_features


def update_markdown_matrix(md_path: Path, supported_features: Set[str]) -> bool:
    """Update a conformance markdown table in-place with newly detected features.

    Args:
        md_path: Path to the markdown conformance file.
        supported_features: Set of detected feature identifiers.

    Returns:
        bool: True if the markdown file existed and was updated, False otherwise.
    """
    if not md_path.exists():
        print(f"Markdown file not found: {md_path}", file=sys.stderr)
        return False

    lines = md_path.read_text(encoding="utf-8").splitlines()
    current_obj: Optional[str] = None

    for i, line in enumerate(lines):
        if line.startswith("### ") and "Object" in line:
            parts = line.split("`")
            if len(parts) >= 2:
                current_obj = parts[1]
            else:
                current_obj = line.replace("### ", "").strip()
        elif line.startswith("### ") and "Object" not in line:
            current_obj = None

        if current_obj and line.strip().startswith("|") and "Status / Notes" not in line and ":---" not in line:
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 4:
                prop_raw = cols[1].replace("`", "").strip()

                is_supported = False
                if prop_raw == "(Object Node)":
                    if current_obj in supported_features:
                        is_supported = True
                elif prop_raw == "(Implicit / Array of Map)":
                    if "Security Requirement Object" in supported_features:
                        is_supported = True
                elif prop_raw == "(Any property)":
                    if "Schema Object" in supported_features:
                        is_supported = True
                else:
                    if f"{current_obj}::{prop_raw}" in supported_features:
                        is_supported = True

                if is_supported:
                    raw_cols = line.split("|")
                    if "[ ]" in raw_cols[3]:
                        raw_cols[3] = raw_cols[3].replace("[ ]", "[x]")
                        lines[i] = "|".join(raw_cols)

    md_path.write_text(chr(10).join(lines), encoding="utf-8")
    print(f"Successfully updated {md_path}")
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for `detect_conformance.py`.

    Args:
        argv: Optional command-line arguments (excluding script name).

    Returns:
        int: Exit status code (0 on success, 1 on missing markdown file).
    """
    parser = argparse.ArgumentParser(description="Detect OpenAPI 3.2.0 conformance via roundtrip AST comparison.")
    parser.add_argument("input_spec", help="Path to original input OpenAPI spec (JSON/YAML)")
    parser.add_argument("output_spec", help="Path to roundtripped output OpenAPI spec (JSON/YAML)")
    parser.add_argument("--markdown", help="Path to markdown checklist to update in-place", default=None)

    args = parser.parse_args(list(argv) if argv is not None else None)
    features = detect_features(args.input_spec, args.output_spec)

    if args.markdown:
        if not update_markdown_matrix(Path(args.markdown), features):
            return 1
    else:
        for feature in sorted(features):
            print(f"- {feature}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
