"""Step definitions for features/schemas.feature.

Exercises the real scantling files under schemas/, per the Scantling
agreement's referencing requirement for the `schemas` path in RIGGING.md.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import json
import re

from behave import given, when, then

from support import REPO_ROOT

DRAFT_SCHEMA_RE = re.compile(r"^https?://json-schema\.org/draft[-/][^\s]*schema#?$")


@given('the schema file "{path}"')
def step_schema_file(context, path):
    context.schema_path = REPO_ROOT / path
    context.schema_text = context.schema_path.read_text(encoding="utf-8")


@when('it is validated as a JSON Schema document')
def step_validate_schema(context):
    try:
        context.schema_doc = json.loads(context.schema_text)
        context.schema_parse_error = None
    except json.JSONDecodeError as exc:
        context.schema_doc = None
        context.schema_parse_error = exc


@then('it parses as valid JSON')
def step_parses_json(context):
    assert context.schema_parse_error is None, context.schema_parse_error
    assert isinstance(context.schema_doc, dict), context.schema_doc


@then('its "$schema" field declares a JSON Schema draft')
def step_schema_field_draft(context):
    value = context.schema_doc.get("$schema")
    assert value, "missing $schema field"
    assert DRAFT_SCHEMA_RE.match(value), (
        f"$schema {value!r} does not declare a recognized JSON Schema draft"
    )
