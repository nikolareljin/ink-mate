#!/usr/bin/env python3
"""Validate protocol schemas and bundled examples without network access."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, RefResolver


ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    with (ROOT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    schemas = {
        name: load(name)
        for name in (
            "card.schema.json",
            "interaction-response.schema.json",
            "snapshot.schema.json",
        )
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    interaction_schema = schemas["interaction-response.schema.json"]
    resolver = RefResolver(
        base_uri=(ROOT.as_uri() + "/"),
        referrer=interaction_schema,
        store={schema["$id"]: schema for schema in schemas.values()},
    )
    validator = Draft202012Validator(
        interaction_schema,
        resolver=resolver,
        format_checker=FormatChecker(),
    )
    validator.validate(load("examples/interaction-response.json"))


if __name__ == "__main__":
    main()
