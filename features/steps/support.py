"""Shared verification support: real subprocess and fixture helpers.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RIGGING_PATH = REPO_ROOT / "RIGGING.md"


def new_tmp_dir(context, prefix):
    """Create a namespaced temp dir and register its teardown on the context."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    context.add_cleanup(shutil.rmtree, path, ignore_errors=True)
    return path


def run(cmd, cwd=None, env=None, timeout=None):
    """Run a real subprocess and capture its result."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def read_rigging_command(key):
    """Read the single-line backtick command value for `key` under RIGGING.md's
    ## Commands heading, per the Rigging read contract."""
    text = RIGGING_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^- {re.escape(key)}: `(.+)`$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"no {key!r} command found in RIGGING.md")
    return match.group(1)


DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

_JSON_SCHEMA_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def validate_json_schema(instance, schema, path="$"):
    """Minimal structural JSON Schema conformance check.

    Covers the keywords project schemas use: type (string or list of
    strings), enum, required, properties, additionalProperties, minLength,
    minItems, items, minimum, and format (date-time only). No jsonschema
    library is installed under RIGGING.md's locked dependency policy.
    """
    errors = []
    schema_type = schema.get("type")
    types = schema_type if isinstance(schema_type, list) else [schema_type] if schema_type else []
    if types:
        ok = False
        for type_name in types:
            python_type = _JSON_SCHEMA_TYPES.get(type_name)
            if python_type is None:
                continue
            if type_name == "integer" and isinstance(instance, bool):
                continue
            if isinstance(instance, python_type):
                ok = True
                break
        if not ok:
            return [f"{path}: expected type in {types}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for required_field in schema.get("required", []):
            if required_field not in instance:
                errors.append(f"{path}: missing required field {required_field!r}")
        for prop, subschema in properties.items():
            if prop in instance:
                errors.extend(validate_json_schema(instance[prop], subschema, f"{path}.{prop}"))
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                errors.append(f"{path}: unexpected properties {extra}")
    elif isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(instance)}")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                errors.extend(validate_json_schema(item, item_schema, f"{path}[{index}]"))
    elif isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path}: string shorter than minLength {min_length}")
        if schema.get("format") == "date-time" and not DATE_TIME_RE.match(instance):
            errors.append(f"{path}: {instance!r} does not match date-time format")
    elif isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: {instance} is less than minimum {minimum}")
    return errors


def run_rigging_command(key, scenario_args=None, cwd=None, timeout=None):
    """Run a RIGGING.md command for real, substituting the {scenario}
    placeholder token with scenario_args (a list of scenario references)
    when the command carries one.

    Runs through a real shell rather than shlex-splitting: the command
    string embeds a shell-double-quoted Python literal (`'\\$'`), and only
    a real shell's double-quote backslash rule reduces it to the intended
    regex end-anchor. shlex.split does not replicate that rule and yields
    a mismatched anchor, a QM-side harness defect rather than a product one.
    """
    template = read_rigging_command(key)
    if scenario_args is not None:
        quoted = " ".join(shlex.quote(a) for a in scenario_args)
        template = template.replace("{scenario}", quoted)
    return subprocess.run(
        template, shell=True, cwd=cwd or REPO_ROOT,
        capture_output=True, text=True, timeout=timeout,
    )
