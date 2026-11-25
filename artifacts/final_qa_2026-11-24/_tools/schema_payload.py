"""Deterministic synthetic payload generator from the live OpenAPI contract.

Only required fields are filled, with harmless `.invalid` identities and
clearly-labelled QA values. Used for local NOVARA QA only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SPEC = json.loads(
    Path(r"D:\NOVARA\artifacts\final_qa_2026-11-24\evidence\openapi.json").read_text(encoding="utf-8")
)


def resolve(schema: dict) -> dict:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = SPEC["components"]["schemas"][name]
    return schema


def value_for(name: str, schema: dict, depth: int = 0):
    s = resolve(schema)
    if "anyOf" in s:
        non_null = [x for x in s["anyOf"] if x.get("type") != "null"]
        return value_for(name, non_null[0] if non_null else {"type": "string"}, depth)
    if "allOf" in s:
        out = {}
        for part in s["allOf"]:
            p = resolve(part)
            if p.get("type") == "object":
                out.update(object_for(p, depth + 1))
        return out or {}
    t = s.get("type")
    if t == "object" or "properties" in s:
        return object_for(s, depth + 1)
    if t == "array":
        item = value_for(name + "_item", s.get("items", {"type": "string"}), depth + 1)
        return [item]
    if "enum" in s and s["enum"]:
        return s["enum"][0]
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return False
    low = name.lower()
    if "email" in low:
        return "qa.synthetic@novara.invalid"
    if "url" in low or "website" in low or "link" in low:
        return "https://example.invalid/qa"
    if "password" in low:
        return "QaSynthetic!2026"
    if "body" in low or "message" in low or "description" in low or "content" in low:
        return "Synthetic QA record. No external delivery."
    if "date" in low:
        return "2026-11-24"
    if "id" in low:
        return "qa-synthetic-id"
    if "token" in low:
        return "qa-synthetic-token"
    if "name" in low or "title" in low or "key" in low or "slug" in low:
        return "QA Synthetic " + name.replace("_", " ")
    if "subject" in low:
        return "Synthetic QA subject"
    return "qa"


def object_for(schema: dict, depth: int = 0) -> dict:
    if depth > 4:
        return {}
    s = resolve(schema)
    props = s.get("properties", {})
    required = s.get("required", [])
    if not required and props:
        # For optional-only bodies, still supply a couple of harmless fields so
        # the endpoint receives a meaningful request rather than an empty body.
        required = list(props.keys())[:2]
    return {k: value_for(k, props[k], depth) for k in required if k in props}


def canonical_path(path: str, method: str) -> str:
    """Map a concrete QA URL back to its OpenAPI template."""
    if path in SPEC["paths"]:
        return path
    m = method.lower()
    candidates = [p for p, ops in SPEC["paths"].items() if m in ops]
    for candidate in sorted(candidates, key=len, reverse=True):
        pattern = "^" + re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(candidate).replace(r"\{", "{").replace(r"\}", "}")) + "$"
        if re.match(pattern, path):
            return candidate
    return path


def body_for(path: str, method: str) -> dict | None:
    op = SPEC["paths"].get(canonical_path(path, method), {}).get(method.lower(), {})
    body = op.get("requestBody")
    if not body:
        return None
    content = body.get("content", {})
    schema = content.get("application/json", {}).get("schema")
    if not schema:
        schema = next(iter(content.values())).get("schema")
    if not schema:
        return None
    return object_for(schema)


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(p, json.dumps(body_for(p, "post"), ensure_ascii=False))
