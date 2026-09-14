"""Step definitions for features/plugin-packaging.feature.

Exercises the real manifest and license files at the repo root, and a
minimal structural JSON Schema conformance check for the schemas/*.schema.json
scantlings referenced by this feature's @contract scenarios. No jsonschema
library is installed under RIGGING.md's locked dependency policy, so
conformance is discharged by a bespoke checker covering exactly the
keywords the two referenced schemas use: type, required, properties,
minLength, minItems, and items.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import json

from behave import given, then

from support import REPO_ROOT


def _load_manifest(context, path):
    full = REPO_ROOT / path
    text = full.read_text(encoding="utf-8")
    doc = json.loads(text)
    entry = {"path": path, "text": text, "doc": doc}
    if not hasattr(context, "manifests"):
        context.manifests = []
    context.manifests.append(entry)


@given('the plugin manifest at "{path}"')
def step_plugin_manifest(context, path):
    _load_manifest(context, path)


@given('the marketplace manifest at "{path}"')
def step_marketplace_manifest(context, path):
    _load_manifest(context, path)


@then('it declares "{field}" as "{value}"')
def step_declares_field(context, field, value):
    doc = context.manifests[-1]["doc"]
    assert doc.get(field) == value, f"{field}: expected {value!r}, got {doc.get(field)!r}"


@then('the two manifests are byte-identical')
def step_byte_identical(context):
    assert len(context.manifests) == 2, context.manifests
    first, second = context.manifests
    assert first["text"] == second["text"], (first["path"], second["path"])


@then('it lists a plugin named "{name}" sourced from "{source}"')
def step_lists_plugin(context, name, source):
    doc = context.manifests[-1]["doc"]
    plugins = doc.get("plugins", [])
    assert any(p.get("name") == name and p.get("source") == source for p in plugins), plugins


@then('a "{filename}" file exists at the repo root')
def step_file_exists(context, filename):
    path = REPO_ROOT / filename
    assert path.is_file(), path
    context.license_path = path


@then('it declares the "{license_name}" license')
def step_declares_license(context, license_name):
    text = context.license_path.read_text(encoding="utf-8")
    assert license_name in text, text


def _validate_schema(instance, schema, path="$"):
    """Minimal structural JSON Schema conformance check.

    Covers exactly the keywords schemas/plugin.schema.json and
    schemas/marketplace.schema.json use: type, required, properties,
    minLength, minItems, items. additionalProperties is not enforced:
    both referenced schemas declare it true.
    """
    errors = []
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(instance, dict):
            return [f"{path}: expected object, got {type(instance).__name__}"]
        for required_field in schema.get("required", []):
            if required_field not in instance:
                errors.append(f"{path}: missing required field {required_field!r}")
        for prop, subschema in schema.get("properties", {}).items():
            if prop in instance:
                errors.extend(_validate_schema(instance[prop], subschema, f"{path}.{prop}"))
    elif schema_type == "array":
        if not isinstance(instance, list):
            return [f"{path}: expected array, got {type(instance).__name__}"]
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(instance)}")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                errors.extend(_validate_schema(item, item_schema, f"{path}[{index}]"))
    elif schema_type == "string":
        if not isinstance(instance, str):
            return [f"{path}: expected string, got {type(instance).__name__}"]
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path}: string shorter than minLength {min_length}")
    return errors


@then('it conforms to the "{label}" schema in "{schema_path}"')
def step_conforms_to_schema(context, label, schema_path):
    schema = json.loads((REPO_ROOT / schema_path).read_text(encoding="utf-8"))
    doc = context.manifests[-1]["doc"]
    errors = _validate_schema(doc, schema)
    assert not errors, f"{label} schema violations: {errors}"
