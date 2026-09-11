"""Step definitions for features/methodology.feature.

These scenarios guard this project's own verification method, per the
Shipshape skill's Harbour flow. The checker logic they exercise is owned
here, in verification support, per the derived verification-conformance
rule set's own note: "A rule's checker logic belongs in the promoted
@conformance scenario's step definitions, written by QM."

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import ast
import json
import re

from behave import given, when, then

from support import REPO_ROOT, new_tmp_dir

TIER_TAGS = {"@logic", "@sandbox"}
SCENARIO_REF_RE = re.compile(r"^features/[^:]+\.feature:.+$")
PLANK_TOKEN_RE = re.compile(r"@planks(?:-provisional)?\(")


# --- watchbill shape ---------------------------------------------------

def check_watchbill_shape(root):
    """Validate watchbill.json shape per the Watchbill policy. Absent is clean."""
    path = root / "watchbill.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"watchbill.json is not valid JSON: {exc}"]
    violations = []
    if not isinstance(data, dict):
        return ["watchbill.json root must be an object of watches"]
    for watch_name, watch in data.items():
        if not re.fullmatch(r"watch\d+", watch_name):
            violations.append(f"unexpected top-level key {watch_name!r}")
            continue
        if not isinstance(watch, dict) or set(watch) != {"scenarios"}:
            violations.append(f"{watch_name}: must contain only 'scenarios'")
            continue
        scenarios = watch["scenarios"]
        if not isinstance(scenarios, list):
            violations.append(f"{watch_name}.scenarios must be an array")
            continue
        for entry in scenarios:
            if not isinstance(entry, str):
                violations.append(f"{watch_name}: entry {entry!r} is not a string")
            elif entry not in TIER_TAGS and not SCENARIO_REF_RE.match(entry):
                violations.append(f"{watch_name}: {entry!r} is not a valid scenario reference or tier tag")
    return violations


@given('no "watchbill.json" file exists at the project root')
def step_no_watchbill(context):
    context.check_root = new_tmp_dir(context, "pce-watchbill-")


@when('the watchbill-shape conformance check runs')
def step_run_watchbill_check(context):
    context.violations = check_watchbill_shape(context.check_root)


@then('the check reports the deck at rest with no shape violation')
def step_deck_at_rest(context):
    assert context.violations == [], context.violations


# --- perturbation quiescence --------------------------------------------

def check_perturbation_quiescence(root):
    hits = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "PERTURBATION" in text:
                hits.append(str(path.relative_to(root)))
    return hits


@given('every file under "{dirname}" carries no "{token}" token')
def step_no_perturbation_token(context, dirname, token):
    root = REPO_ROOT / dirname
    context.perturbation_root = root
    hits = [h for h in check_perturbation_quiescence(root) if True]
    # precondition: real tree currently carries no standing perturbation
    assert hits == [], f"expected no {token!r} token under {dirname}, found: {hits}"


@when('the perturbation-quiescence check runs')
def step_run_perturbation_check(context):
    context.perturbation_hits = check_perturbation_quiescence(context.perturbation_root)


@then('the check reports no standing perturbation')
def step_no_standing_perturbation(context):
    assert context.perturbation_hits == [], context.perturbation_hits


# --- plank form ----------------------------------------------------------

def check_plank_form(root):
    """Every @planks(...) / @planks-provisional(...) token must sit inside a
    docstring that is the first statement of the declaration it describes.
    A token in a bare comment, or in the body of a declaration, is malformed.
    """
    violations = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            violations.append(f"{path.name}: could not parse ({exc})")
            continue
        docstring_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if node.body and isinstance(node.body[0], ast.Expr):
                    first = node.body[0]
                    value = getattr(first, "value", None)
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        start = first.lineno
                        end = getattr(first, "end_lineno", first.lineno)
                        docstring_lines.update(range(start, end + 1))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if PLANK_TOKEN_RE.search(line) and lineno not in docstring_lines:
                violations.append(f"{path.name}:{lineno}: malformed plank outside docstring: {line.strip()}")
    return violations


@given('the rule set at "{path}"')
def step_load_ruleset(context, path):
    context.ruleset = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


@given('a "{token}" token placed in a bare line comment outside any docstring')
def step_plant_bad_plank(context, token):
    context.fixture_dir = new_tmp_dir(context, "pce-plankform-")
    fixture_file = context.fixture_dir / "bad_seam.py"
    fixture_file.write_text(
        "def some_seam():\n"
        '    """A normal docstring, no plank here."""\n'
        f'    # {token}("features/example.feature:Some scenario")\n'
        "    return 1\n",
        encoding="utf-8",
    )


@when('the conformance check runs against the "{rule_id}" rule')
def step_run_conformance_check(context, rule_id):
    assert rule_id == "plank-form", rule_id
    context.violations = check_plank_form(context.fixture_dir)


@then('the check reddens naming the malformed plank')
def step_check_reddens(context):
    assert context.violations, "expected plank-form check to report a violation"
    assert any("bad_seam.py" in v for v in context.violations), context.violations
