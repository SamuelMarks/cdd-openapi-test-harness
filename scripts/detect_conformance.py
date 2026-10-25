"""OpenAPI 3.2.0 conformance detector (`scripts/detect_conformance.py`).

Loads an original OpenAPI specification and a roundtripped output specification,
then walks through both documents structurally to record which OpenAPI objects
and properties were preserved accurately. Optionally updates a Markdown
conformance checklist in-place.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence, Set, Tuple, Union

import yaml

from harness.errors import ConformanceError, JSONDict, JSONValue, SpecificationError

WalkerFn = Callable[[JSONValue, JSONValue], bool]

SCHEMA_KEYWORDS: Tuple[str, ...] = (
    "type",
    "format",
    "title",
    "description",
    "default",
    "multipleOf",
    "maximum",
    "exclusiveMaximum",
    "minimum",
    "exclusiveMinimum",
    "maxLength",
    "minLength",
    "pattern",
    "maxItems",
    "minItems",
    "uniqueItems",
    "maxProperties",
    "minProperties",
    "required",
    "enum",
    "const",
    "$schema",
    "$id",
    "$anchor",
    "$dynamicRef",
    "$dynamicAnchor",
    "readOnly",
    "writeOnly",
    "deprecated",
    "examples",
)


class ConformanceDetector:
    """Walks input and output OpenAPI ASTs to detect preserved OAS 3.2.0 features.

    Attributes:
        supported_features: Set of recorded feature identifiers (`Object` or `Object::property`).
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
        self.supported_features.add(obj)
        if prop:
            self.supported_features.add(f"{obj}::{prop}")

    @staticmethod
    def is_ref(node: JSONValue) -> bool:
        """Return whether a node is a JSON Reference object containing `$ref`.

        Args:
            node: AST node to inspect.

        Returns:
            bool: True if `node` is a dict containing `'$ref'`.
        """
        return isinstance(node, dict) and "$ref" in node

    @staticmethod
    def _values_match(in_val: JSONValue, out_val: JSONValue) -> bool:
        """Compare two specification values for recursive structural equivalence.

        Args:
            in_val: Value from the original input specification.
            out_val: Value from the roundtripped output specification.

        Returns:
            bool: True if the values match in type and recursive structure.
        """
        if isinstance(in_val, bool) or isinstance(out_val, bool):
            return type(in_val) is type(out_val) and in_val == out_val
        if isinstance(in_val, (int, float)) and isinstance(out_val, (int, float)):
            return in_val == out_val
        if type(in_val) is not type(out_val):
            return False
        if isinstance(in_val, dict) and isinstance(out_val, dict):
            return all(k in out_val and ConformanceDetector._values_match(v, out_val[k]) for k, v in in_val.items())
        if isinstance(in_val, list) and isinstance(out_val, list):
            return len(in_val) == len(out_val) and all(
                ConformanceDetector._values_match(a, b) for a, b in zip(in_val, out_val)
            )
        return in_val == out_val

    def _check_ref(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Verify whether `in_node` is a Reference Object and record preserved fields.

        Args:
            in_node: Input AST node.
            out_node: Output AST node.

        Returns:
            bool: True if `in_node` is a Reference Object (handled here), False otherwise.
        """
        if not isinstance(in_node, dict) or not self.is_ref(in_node):
            return False
        if isinstance(out_node, dict) and self.is_ref(out_node) and in_node.get("$ref") == out_node.get("$ref"):
            self.record("Reference Object", "$ref")
            for k in ("summary", "description"):
                if k in in_node and k in out_node and self._values_match(in_node[k], out_node[k]):
                    self.record("Reference Object", k)
        return True

    def walk_list(self, in_list: JSONValue, out_list: JSONValue, walk_fn: WalkerFn) -> bool:
        """Walk two parallel lists of OpenAPI objects, matching by key or position.

        Args:
            in_list: Input list of AST nodes.
            out_list: Output list of AST nodes.
            walk_fn: Walker method to invoke on each matched element pair.

        Returns:
            bool: True if at least one element pair matched (or both lists are empty).
        """
        if not isinstance(in_list, list) or not isinstance(out_list, list):
            return False
        if not in_list and not out_list:
            return True
        matched_any = False
        for i, in_item in enumerate(in_list):
            matched_out: JSONValue = None
            if isinstance(in_item, dict):
                for key in ("name", "url", "$ref"):
                    if key in in_item:
                        for out_item in out_list:
                            if isinstance(out_item, dict) and out_item.get(key) == in_item[key]:
                                matched_out = out_item
                                break
                        if matched_out is not None:
                            break
            if matched_out is None and i < len(out_list):
                matched_out = out_list[i]
            if matched_out is not None and walk_fn(in_item, matched_out):
                matched_any = True
        return matched_any

    def walk_dict(self, in_dict: JSONValue, out_dict: JSONValue, walk_fn: WalkerFn) -> bool:
        """Walk two parallel dictionaries of OpenAPI objects keyed by string identifier.

        Args:
            in_dict: Input dictionary of AST nodes.
            out_dict: Output dictionary of AST nodes.
            walk_fn: Walker method to invoke on each shared key's value pair.

        Returns:
            bool: True if at least one entry matched (or both dicts are empty).
        """
        if not isinstance(in_dict, dict) or not isinstance(out_dict, dict):
            return False
        if not in_dict and not out_dict:
            return True
        matched_any = False
        for k, in_val in in_dict.items():
            if k in out_dict and walk_fn(in_val, out_dict[k]):
                matched_any = True
        return matched_any

    def _record_matching_scalars(
        self,
        obj_name: str,
        in_node: JSONDict,
        out_node: JSONDict,
        keys: Tuple[str, ...],
    ) -> bool:
        """Check and record scalar/collection properties that match between `in_node` and `out_node`.

        Args:
            obj_name: OpenAPI object name to record.
            in_node: Input object dictionary.
            out_node: Output object dictionary.
            keys: Property names to compare and record.

        Returns:
            bool: True if at least one property matched.
        """
        matched = False
        for k in keys:
            if k in in_node and k in out_node and self._values_match(in_node[k], out_node[k]):
                self.record(obj_name, k)
                matched = True
        return matched

    def walk_contact(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Contact Object.

        Args:
            in_node: Input Contact Object.
            out_node: Output Contact Object.

        Returns:
            bool: True if any Contact Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        return self._record_matching_scalars(
            "Contact Object",
            in_node,
            out_node,
            ("name", "url", "email"),
        )

    def walk_license(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a License Object.

        Args:
            in_node: Input License Object.
            out_node: Output License Object.

        Returns:
            bool: True if any License Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        return self._record_matching_scalars(
            "License Object",
            in_node,
            out_node,
            ("name", "identifier", "url"),
        )

    def walk_info(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an Info Object.

        Args:
            in_node: Input Info Object.
            out_node: Output Info Object.

        Returns:
            bool: True if any Info Object property or child matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Info Object",
            in_node,
            out_node,
            ("title", "summary", "description", "termsOfService", "version"),
        )
        if (
            "contact" in in_node
            and "contact" in out_node
            and self.walk_contact(in_node["contact"], out_node["contact"])
        ):
            self.record("Info Object", "contact")
            matched = True
        if (
            "license" in in_node
            and "license" in out_node
            and self.walk_license(in_node["license"], out_node["license"])
        ):
            self.record("Info Object", "license")
            matched = True
        return matched

    def walk_server_var(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Server Variable Object.

        Args:
            in_node: Input Server Variable Object.
            out_node: Output Server Variable Object.

        Returns:
            bool: True if any Server Variable Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        return self._record_matching_scalars(
            "Server Variable Object",
            in_node,
            out_node,
            ("enum", "default", "description"),
        )

    def walk_server(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Server Object.

        Args:
            in_node: Input Server Object.
            out_node: Output Server Object.

        Returns:
            bool: True if any Server Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Server Object",
            in_node,
            out_node,
            ("url", "description", "name"),
        )
        if (
            "variables" in in_node
            and "variables" in out_node
            and self.walk_dict(in_node["variables"], out_node["variables"], self.walk_server_var)
        ):
            self.record("Server Object", "variables")
            matched = True
        return matched

    def walk_external_docs(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an External Documentation Object.

        Args:
            in_node: Input External Documentation Object.
            out_node: Output External Documentation Object.

        Returns:
            bool: True if any External Documentation Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        return self._record_matching_scalars(
            "External Documentation Object",
            in_node,
            out_node,
            ("description", "url"),
        )

    def walk_schema(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Schema Object, including JSON Schema keywords, Discriminator, and XML.

        Args:
            in_node: Input Schema Object or boolean schema.
            out_node: Output Schema Object or boolean schema.

        Returns:
            bool: True if the Schema Object matched.
        """
        if isinstance(in_node, bool) and isinstance(out_node, bool):
            if in_node == out_node:
                self.record("Schema Object")
                return True
            return False
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True

        if not in_node and not out_node:
            self.record("Schema Object")
            return True

        matched = self._record_matching_scalars("Schema Object", in_node, out_node, SCHEMA_KEYWORDS)

        if "discriminator" in in_node and "discriminator" in out_node:
            in_d = in_node["discriminator"]
            out_d = out_node["discriminator"]
            if (
                isinstance(in_d, dict)
                and isinstance(out_d, dict)
                and self._record_matching_scalars(
                    "Discriminator Object",
                    in_d,
                    out_d,
                    ("propertyName", "mapping", "defaultMapping"),
                )
            ):
                self.record("Schema Object", "discriminator")
                matched = True

        if "xml" in in_node and "xml" in out_node:
            in_x = in_node["xml"]
            out_x = out_node["xml"]
            if (
                isinstance(in_x, dict)
                and isinstance(out_x, dict)
                and self._record_matching_scalars(
                    "XML Object",
                    in_x,
                    out_x,
                    ("name", "namespace", "prefix", "attribute", "wrapped", "nodeType"),
                )
            ):
                self.record("Schema Object", "xml")
                matched = True

        if (
            "externalDocs" in in_node
            and "externalDocs" in out_node
            and self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
        ):
            self.record("Schema Object", "externalDocs")
            matched = True

        if (
            "example" in in_node
            and "example" in out_node
            and self._values_match(in_node["example"], out_node["example"])
        ):
            self.record("Schema Object", "example")
            matched = True

        if "properties" in in_node and "properties" in out_node:
            in_props = in_node["properties"]
            out_props = out_node["properties"]
            if isinstance(in_props, dict) and isinstance(out_props, dict):
                for prop_name, prop_schema in in_props.items():
                    if prop_name in out_props and self.walk_schema(prop_schema, out_props[prop_name]):
                        matched = True

        if (
            "items" in in_node
            and "items" in out_node
            and isinstance(in_node["items"], dict)
            and isinstance(out_node["items"], dict)
            and self.walk_schema(in_node["items"], out_node["items"])
        ):
            matched = True

        for comb in ("allOf", "anyOf", "oneOf"):
            if comb in in_node and comb in out_node and self.walk_list(in_node[comb], out_node[comb], self.walk_schema):
                matched = True

        if "not" in in_node and "not" in out_node and self.walk_schema(in_node["not"], out_node["not"]):
            matched = True

        if (
            "additionalProperties" in in_node
            and "additionalProperties" in out_node
            and isinstance(in_node["additionalProperties"], (dict, bool))
            and isinstance(out_node["additionalProperties"], (dict, bool))
            and self.walk_schema(in_node["additionalProperties"], out_node["additionalProperties"])
        ):
            matched = True

        if matched:
            self.record("Schema Object")
        return matched

    def walk_example(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an Example Object.

        Args:
            in_node: Input Example Object.
            out_node: Output Example Object.

        Returns:
            bool: True if any Example Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        return self._record_matching_scalars(
            "Example Object",
            in_node,
            out_node,
            ("summary", "description", "value", "dataValue", "serializedValue", "externalValue"),
        )

    def walk_header(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Header Object.

        Args:
            in_node: Input Header Object.
            out_node: Output Header Object.

        Returns:
            bool: True if any Header Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
            "Header Object",
            in_node,
            out_node,
            ("description", "required", "deprecated", "style", "explode", "example"),
        )
        if "schema" in in_node and "schema" in out_node and self.walk_schema(in_node["schema"], out_node["schema"]):
            self.record("Header Object", "schema")
            matched = True
        if (
            "examples" in in_node
            and "examples" in out_node
            and self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
        ):
            self.record("Header Object", "examples")
            matched = True
        if (
            "content" in in_node
            and "content" in out_node
            and self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
        ):
            self.record("Header Object", "content")
            matched = True
        return matched

    def walk_encoding(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an Encoding Object.

        Args:
            in_node: Input Encoding Object.
            out_node: Output Encoding Object.

        Returns:
            bool: True if any Encoding Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Encoding Object",
            in_node,
            out_node,
            ("contentType", "style", "explode", "allowReserved"),
        )
        if (
            "headers" in in_node
            and "headers" in out_node
            and self.walk_dict(in_node["headers"], out_node["headers"], self.walk_header)
        ):
            self.record("Encoding Object", "headers")
            matched = True
        if (
            "encoding" in in_node
            and "encoding" in out_node
            and self.walk_dict(in_node["encoding"], out_node["encoding"], self.walk_encoding)
        ):
            self.record("Encoding Object", "encoding")
            matched = True
        if (
            "prefixEncoding" in in_node
            and "prefixEncoding" in out_node
            and self.walk_list(in_node["prefixEncoding"], out_node["prefixEncoding"], self.walk_encoding)
        ):
            self.record("Encoding Object", "prefixEncoding")
            matched = True
        if (
            "itemEncoding" in in_node
            and "itemEncoding" in out_node
            and self.walk_encoding(in_node["itemEncoding"], out_node["itemEncoding"])
        ):
            self.record("Encoding Object", "itemEncoding")
            matched = True
        return matched

    def walk_media_type(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Media Type Object.

        Args:
            in_node: Input Media Type Object.
            out_node: Output Media Type Object.

        Returns:
            bool: True if any Media Type Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars("Media Type Object", in_node, out_node, ("example",))
        if "schema" in in_node and "schema" in out_node and self.walk_schema(in_node["schema"], out_node["schema"]):
            self.record("Media Type Object", "schema")
            matched = True
        if (
            "itemSchema" in in_node
            and "itemSchema" in out_node
            and self.walk_schema(in_node["itemSchema"], out_node["itemSchema"])
        ):
            self.record("Media Type Object", "itemSchema")
            matched = True
        if (
            "examples" in in_node
            and "examples" in out_node
            and self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
        ):
            self.record("Media Type Object", "examples")
            matched = True
        if (
            "encoding" in in_node
            and "encoding" in out_node
            and self.walk_dict(in_node["encoding"], out_node["encoding"], self.walk_encoding)
        ):
            self.record("Media Type Object", "encoding")
            matched = True
        if (
            "prefixEncoding" in in_node
            and "prefixEncoding" in out_node
            and self.walk_list(in_node["prefixEncoding"], out_node["prefixEncoding"], self.walk_encoding)
        ):
            self.record("Media Type Object", "prefixEncoding")
            matched = True
        if (
            "itemEncoding" in in_node
            and "itemEncoding" in out_node
            and self.walk_encoding(in_node["itemEncoding"], out_node["itemEncoding"])
        ):
            self.record("Media Type Object", "itemEncoding")
            matched = True
        return matched

    def walk_parameter(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Parameter Object.

        Args:
            in_node: Input Parameter Object.
            out_node: Output Parameter Object.

        Returns:
            bool: True if any Parameter Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
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
        if "schema" in in_node and "schema" in out_node and self.walk_schema(in_node["schema"], out_node["schema"]):
            self.record("Parameter Object", "schema")
            matched = True
        if (
            "examples" in in_node
            and "examples" in out_node
            and self.walk_dict(in_node["examples"], out_node["examples"], self.walk_example)
        ):
            self.record("Parameter Object", "examples")
            matched = True
        if (
            "content" in in_node
            and "content" in out_node
            and self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
        ):
            self.record("Parameter Object", "content")
            matched = True
        return matched

    def walk_request_body(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Request Body Object.

        Args:
            in_node: Input Request Body Object.
            out_node: Output Request Body Object.

        Returns:
            bool: True if any Request Body Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
            "Request Body Object",
            in_node,
            out_node,
            ("description", "required"),
        )
        if (
            "content" in in_node
            and "content" in out_node
            and self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
        ):
            self.record("Request Body Object", "content")
            matched = True
        return matched

    def walk_link(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Link Object.

        Args:
            in_node: Input Link Object.
            out_node: Output Link Object.

        Returns:
            bool: True if any Link Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
            "Link Object",
            in_node,
            out_node,
            ("operationRef", "operationId", "parameters", "requestBody", "description"),
        )
        if "server" in in_node and "server" in out_node and self.walk_server(in_node["server"], out_node["server"]):
            self.record("Link Object", "server")
            matched = True
        return matched

    def walk_response(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Response Object.

        Args:
            in_node: Input Response Object.
            out_node: Output Response Object.

        Returns:
            bool: True if any Response Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
            "Response Object",
            in_node,
            out_node,
            ("summary", "description"),
        )
        if (
            "headers" in in_node
            and "headers" in out_node
            and self.walk_dict(in_node["headers"], out_node["headers"], self.walk_header)
        ):
            self.record("Response Object", "headers")
            matched = True
        if (
            "content" in in_node
            and "content" in out_node
            and self.walk_dict(in_node["content"], out_node["content"], self.walk_media_type)
        ):
            self.record("Response Object", "content")
            matched = True
        if (
            "links" in in_node
            and "links" in out_node
            and self.walk_dict(in_node["links"], out_node["links"], self.walk_link)
        ):
            self.record("Response Object", "links")
            matched = True
        return matched

    def walk_responses(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Responses Object container.

        Args:
            in_node: Input Responses Object.
            out_node: Output Responses Object.

        Returns:
            bool: True if any status code or default response matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = False
        for code, resp in in_node.items():
            if code.startswith("x-"):
                continue
            if code in out_node and self.walk_response(resp, out_node[code]):
                if code == "default":
                    self.record("Responses Object", "default")
                else:
                    self.record("Responses Object", "{statusCode}")
                matched = True
        return matched

    def walk_callback(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Callback Object.

        Args:
            in_node: Input Callback Object.
            out_node: Output Callback Object.

        Returns:
            bool: True if any callback expression matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = False
        for expr, path_item in in_node.items():
            if expr.startswith("x-"):
                continue
            if expr in out_node and self.walk_path_item(path_item, out_node[expr]):
                self.record("Callback Object", "{expression}")
                matched = True
        return matched

    def walk_operation(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an Operation Object.

        Args:
            in_node: Input Operation Object.
            out_node: Output Operation Object.

        Returns:
            bool: True if any Operation Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Operation Object",
            in_node,
            out_node,
            ("tags", "summary", "description", "operationId", "deprecated"),
        )
        if (
            "externalDocs" in in_node
            and "externalDocs" in out_node
            and self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
        ):
            self.record("Operation Object", "externalDocs")
            matched = True
        if (
            "parameters" in in_node
            and "parameters" in out_node
            and self.walk_list(in_node["parameters"], out_node["parameters"], self.walk_parameter)
        ):
            self.record("Operation Object", "parameters")
            matched = True
        if (
            "requestBody" in in_node
            and "requestBody" in out_node
            and self.walk_request_body(in_node["requestBody"], out_node["requestBody"])
        ):
            self.record("Operation Object", "requestBody")
            matched = True
        if (
            "responses" in in_node
            and "responses" in out_node
            and self.walk_responses(in_node["responses"], out_node["responses"])
        ):
            self.record("Operation Object", "responses")
            matched = True
        if (
            "callbacks" in in_node
            and "callbacks" in out_node
            and self.walk_dict(in_node["callbacks"], out_node["callbacks"], self.walk_callback)
        ):
            self.record("Operation Object", "callbacks")
            matched = True
        if (
            "security" in in_node
            and "security" in out_node
            and isinstance(out_node["security"], list)
            and self._values_match(in_node["security"], out_node["security"])
        ):
            self.record("Operation Object", "security")
            self.record("Security Requirement Object")
            matched = True
        if (
            "servers" in in_node
            and "servers" in out_node
            and self.walk_list(in_node["servers"], out_node["servers"], self.walk_server)
        ):
            self.record("Operation Object", "servers")
            matched = True
        return matched

    def walk_path_item(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Path Item Object.

        Args:
            in_node: Input Path Item Object.
            out_node: Output Path Item Object.

        Returns:
            bool: True if any Path Item Object property or operation matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Path Item Object",
            in_node,
            out_node,
            ("$ref", "summary", "description"),
        )
        for method in ("get", "put", "post", "delete", "options", "head", "patch", "trace", "query"):
            if method in in_node and method in out_node and self.walk_operation(in_node[method], out_node[method]):
                self.record("Path Item Object", method)
                matched = True
        if (
            "additionalOperations" in in_node
            and "additionalOperations" in out_node
            and self.walk_dict(in_node["additionalOperations"], out_node["additionalOperations"], self.walk_operation)
        ):
            self.record("Path Item Object", "additionalOperations")
            matched = True
        if (
            "servers" in in_node
            and "servers" in out_node
            and self.walk_list(in_node["servers"], out_node["servers"], self.walk_server)
        ):
            self.record("Path Item Object", "servers")
            matched = True
        if (
            "parameters" in in_node
            and "parameters" in out_node
            and self.walk_list(in_node["parameters"], out_node["parameters"], self.walk_parameter)
        ):
            self.record("Path Item Object", "parameters")
            matched = True
        return matched

    def walk_paths(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Paths Object container.

        Args:
            in_node: Input Paths Object.
            out_node: Output Paths Object.

        Returns:
            bool: True if at least one path entry matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = False
        for path, item in in_node.items():
            if path.startswith("x-"):
                continue
            if path in out_node and self.walk_path_item(item, out_node[path]):
                self.record("Paths Object", "/{path}")
                matched = True
        return matched

    def walk_oauth_flow(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an OAuth Flow Object.

        Args:
            in_node: Input OAuth Flow Object.
            out_node: Output OAuth Flow Object.

        Returns:
            bool: True if any OAuth Flow Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        return self._record_matching_scalars(
            "OAuth Flow Object",
            in_node,
            out_node,
            ("authorizationUrl", "deviceAuthorizationUrl", "tokenUrl", "refreshUrl", "scopes"),
        )

    def walk_oauth_flows(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk an OAuth Flows Object.

        Args:
            in_node: Input OAuth Flows Object.
            out_node: Output OAuth Flows Object.

        Returns:
            bool: True if any OAuth flow matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = False
        for flow in ("implicit", "password", "clientCredentials", "authorizationCode", "deviceAuthorization"):
            if flow in in_node and flow in out_node and self.walk_oauth_flow(in_node[flow], out_node[flow]):
                self.record("OAuth Flows Object", flow)
                matched = True
        return matched

    def walk_security_scheme(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Security Scheme Object.

        Args:
            in_node: Input Security Scheme Object.
            out_node: Output Security Scheme Object.

        Returns:
            bool: True if any Security Scheme Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        if self._check_ref(in_node, out_node):
            return True
        matched = self._record_matching_scalars(
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
        if "flows" in in_node and "flows" in out_node and self.walk_oauth_flows(in_node["flows"], out_node["flows"]):
            self.record("Security Scheme Object", "flows")
            matched = True
        return matched

    def walk_components(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Components Object.

        Args:
            in_node: Input Components Object.
            out_node: Output Components Object.

        Returns:
            bool: True if any component collection matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        mapping: Tuple[Tuple[str, WalkerFn], ...] = (
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
        )
        matched = False
        for key, fn in mapping:
            if key in in_node and key in out_node and self.walk_dict(in_node[key], out_node[key], fn):
                self.record("Components Object", key)
                matched = True
        return matched

    def walk_tag(self, in_node: JSONValue, out_node: JSONValue) -> bool:
        """Walk a Tag Object.

        Args:
            in_node: Input Tag Object.
            out_node: Output Tag Object.

        Returns:
            bool: True if any Tag Object property matched.
        """
        if not isinstance(in_node, dict) or not isinstance(out_node, dict):
            return False
        matched = self._record_matching_scalars(
            "Tag Object",
            in_node,
            out_node,
            ("name", "summary", "description", "parent", "kind"),
        )
        if (
            "externalDocs" in in_node
            and "externalDocs" in out_node
            and self.walk_external_docs(in_node["externalDocs"], out_node["externalDocs"])
        ):
            self.record("Tag Object", "externalDocs")
            matched = True
        return matched

    def walk_openapi_doc(self, in_doc: JSONValue, out_doc: JSONValue) -> bool:
        """Walk the root OpenAPI Object.

        Args:
            in_doc: Parsed input OpenAPI document.
            out_doc: Parsed output OpenAPI document.

        Returns:
            bool: True if any root OpenAPI Object property or child matched.
        """
        if not isinstance(in_doc, dict) or not isinstance(out_doc, dict):
            return False
        matched = self._record_matching_scalars(
            "OpenAPI Object",
            in_doc,
            out_doc,
            ("openapi", "$self", "jsonSchemaDialect"),
        )
        if "info" in in_doc and "info" in out_doc and self.walk_info(in_doc["info"], out_doc["info"]):
            self.record("OpenAPI Object", "info")
            matched = True
        if (
            "servers" in in_doc
            and "servers" in out_doc
            and self.walk_list(in_doc["servers"], out_doc["servers"], self.walk_server)
        ):
            self.record("OpenAPI Object", "servers")
            matched = True
        if "paths" in in_doc and "paths" in out_doc and self.walk_paths(in_doc["paths"], out_doc["paths"]):
            self.record("OpenAPI Object", "paths")
            matched = True
        if (
            "webhooks" in in_doc
            and "webhooks" in out_doc
            and self.walk_dict(in_doc["webhooks"], out_doc["webhooks"], self.walk_path_item)
        ):
            self.record("OpenAPI Object", "webhooks")
            matched = True
        if (
            "components" in in_doc
            and "components" in out_doc
            and self.walk_components(in_doc["components"], out_doc["components"])
        ):
            self.record("OpenAPI Object", "components")
            matched = True
        if (
            "security" in in_doc
            and "security" in out_doc
            and isinstance(out_doc["security"], list)
            and self._values_match(in_doc["security"], out_doc["security"])
        ):
            self.record("OpenAPI Object", "security")
            self.record("Security Requirement Object")
            matched = True
        if "tags" in in_doc and "tags" in out_doc and self.walk_list(in_doc["tags"], out_doc["tags"], self.walk_tag):
            self.record("OpenAPI Object", "tags")
            matched = True
        if (
            "externalDocs" in in_doc
            and "externalDocs" in out_doc
            and self.walk_external_docs(in_doc["externalDocs"], out_doc["externalDocs"])
        ):
            self.record("OpenAPI Object", "externalDocs")
            matched = True
        return matched


def load_doc(path: Path) -> JSONDict:
    """Load a JSON or YAML OpenAPI specification document from disk.

    Args:
        path: Path to the JSON or YAML file.

    Returns:
        JSONDict: Parsed dictionary, or empty dictionary if top-level is not a mapping.

    Raises:
        SpecificationError: If the file cannot be read or parsed as JSON/YAML.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecificationError(str(path), str(exc)) from exc

    loaded: JSONValue
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        try:
            loaded = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise SpecificationError(str(path), str(exc)) from exc

    if isinstance(loaded, dict):
        return loaded
    return {}


def detect_features(input_spec: Union[str, Path], output_spec: Union[str, Path]) -> Set[str]:
    """Compare two OpenAPI specification files and return the set of preserved features.

    Args:
        input_spec: Path to the original input OpenAPI specification.
        output_spec: Path to the roundtripped output OpenAPI specification.

    Returns:
        Set[str]: Supported feature keys discovered during the AST walk.
    """
    in_doc = load_doc(Path(input_spec))
    out_doc = load_doc(Path(output_spec))
    detector = ConformanceDetector()
    detector.walk_openapi_doc(in_doc, out_doc)
    return detector.supported_features


def update_markdown_matrix(md_path: Path, supported_features: Set[str]) -> bool:
    """Update a Markdown conformance checklist in-place with `[x]` for supported features.

    Args:
        md_path: Path to the target Markdown checklist file.
        supported_features: Set of supported feature identifiers.

    Returns:
        bool: True on successful update.

    Raises:
        ConformanceError: If `md_path` does not exist on disk.
    """
    if not md_path.exists():
        print(f"Error: Markdown file {md_path} not found.", file=sys.stderr)
        raise ConformanceError(f"Error: Markdown file {md_path} not found.")

    lines = md_path.read_text(encoding="utf-8").splitlines()
    current_obj: Optional[str] = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("### "):
            header_text = stripped[4:].strip()
            if header_text.startswith("`") and header_text.endswith("`"):
                current_obj = header_text[1:-1]
            elif "Object" in header_text:
                current_obj = header_text
            else:
                current_obj = None

        elif current_obj and stripped.startswith("|") and stripped.endswith("|"):
            cols = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cols) >= 3 and cols[0] not in ("Property", ":---"):
                prop_raw = cols[0]
                if prop_raw.startswith("`") and prop_raw.endswith("`"):
                    prop_raw = prop_raw[1:-1]

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
        int: Exit status code (0 on success, 1 on missing markdown or specification error).
    """
    parser = argparse.ArgumentParser(description="Detect OpenAPI 3.2.0 conformance via roundtrip AST comparison.")
    parser.add_argument("input_spec", help="Path to original input OpenAPI spec (JSON/YAML)")
    parser.add_argument("output_spec", help="Path to roundtripped output OpenAPI spec (JSON/YAML)")
    parser.add_argument("--markdown", help="Path to markdown checklist to update in-place", default=None)

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        features = detect_features(args.input_spec, args.output_spec)
        if args.markdown:
            update_markdown_matrix(Path(args.markdown), features)
        else:
            for feature in sorted(features):
                print(f"- {feature}")
    except (ConformanceError, SpecificationError) as exc:
        return exc.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
