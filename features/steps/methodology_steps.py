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
from pathlib import Path

from behave import given, when, then

from support import REPO_ROOT, new_tmp_dir, run_rigging_command

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
    if rule_id == "plank-form":
        context.violations = check_plank_form(context.fixture_dir)
    elif rule_id == "plank-coverage":
        context.violations = check_plank_coverage(context.coverage_steps_dir, context.coverage_impl_dir)
    else:
        raise ValueError(f"unknown rule_id {rule_id!r}")


@then('the check reddens naming the malformed plank')
def step_check_reddens(context):
    assert context.violations, "expected plank-form check to report a violation"
    assert any("bad_seam.py" in v for v in context.violations), context.violations


# --- plank coverage --------------------------------------------------------

WHEN_PATTERN_RE = re.compile(r"@when\(\s*['\"](.+?)['\"]\s*\)")
PLANK_STRING_RE = re.compile(r"@planks\(\s*['\"](.+?)['\"]\s*\)")


def check_plank_coverage(steps_dir, impl_dir):
    """Every When-bound step-definition pattern is behaviour-bearing, per the
    scenario-writing agreement (When is one named action). It needs at least
    one exact-string @planks(...) match somewhere under impl_dir. Given/Then
    patterns are setup or assertion and carry no coverage obligation, per the
    Planking agreement.
    """
    patterns = []
    for path in sorted(Path(steps_dir).rglob("*.py")):
        patterns.extend(WHEN_PATTERN_RE.findall(path.read_text(encoding="utf-8")))

    plank_strings = set()
    for path in sorted(Path(impl_dir).rglob("*.py")):
        plank_strings.update(PLANK_STRING_RE.findall(path.read_text(encoding="utf-8")))

    return [p for p in patterns if p not in plank_strings]


@given('a behaviour-bearing step-definition pattern reported by step-usage with no matching plank token in the implementation paths')
def step_plant_missing_plank(context):
    context.fixture_dir = new_tmp_dir(context, "pce-plankcoverage-")
    steps_dir = context.fixture_dir / "steps"
    steps_dir.mkdir()
    (steps_dir / "orphan_steps.py").write_text(
        "from behave import when\n\n"
        "@when('a doubloon is minted')\n"
        "def step_impl(context):\n"
        "    pass\n",
        encoding="utf-8",
    )
    impl_dir = context.fixture_dir / "impl"
    impl_dir.mkdir()
    (impl_dir / "seam.py").write_text(
        "def unrelated_seam():\n"
        '    """@planks(\'a different behaviour happens\')"""\n'
        "    return 1\n",
        encoding="utf-8",
    )
    context.coverage_steps_dir = steps_dir
    context.coverage_impl_dir = impl_dir


@then('the check reddens naming the uncovered step-definition pattern')
def step_check_reddens_uncovered(context):
    assert context.violations, "expected plank-coverage check to report a violation"
    assert any("a doubloon is minted" in v for v in context.violations), context.violations


# --- focused command selects one outline example --------------------------

SUMMARY_RE = re.compile(
    r"(?P<passed>\d+) scenarios? passed, (?P<failed>\d+) failed"
    r"(?:, (?P<errored>\d+) error)?, (?P<skipped>\d+) skipped"
)


@given('a scenario reference naming one specific example row of a Scenario Outline')
def step_outline_reference(context):
    context.outline_reference = "features/schemas.feature:A shared schema is valid JSON Schema -- @1.1 "


@when('the "focused" command from RIGGING.md runs against that reference')
def step_run_focused_on_reference(context):
    context.focused_result = run_rigging_command(
        "focused", scenario_args=[context.outline_reference], timeout=120
    )


@then('exactly one scenario runs')
def step_exactly_one_scenario(context):
    output = context.focused_result.stdout + context.focused_result.stderr
    match = SUMMARY_RE.search(output)
    assert match, f"no scenario summary line found: {output}"
    selected = int(match.group("passed")) + int(match.group("failed")) + int(match.group("errored") or 0)
    assert selected == 1, f"expected exactly 1 scenario selected, got {selected}: {output}"


@then('it is the named example, not zero examples and not every example')
def step_named_example(context):
    """Behave's listing prints every example row's concrete step text
    regardless of selection, so text presence alone cannot tell selected
    from unselected. A row's step is bound to a real step-definition
    location only when it actually ran; an unselected row shows "# None".
    """
    output = context.focused_result.stdout + context.focused_result.stderr
    assert re.search(r"schemas/claims\.schema\.json.*schemas_steps\.py", output), output
    assert not re.search(r"schemas/fact-check\.schema\.json.*schemas_steps\.py", output), output
    assert not re.search(r"schemas/state\.schema\.json.*schemas_steps\.py", output), output


# --- lint discharges cleanly ------------------------------------------------

@given('the "lint" command from RIGGING.md')
def step_lint_command(context):
    context.lint_target = "packaging"


@when('it runs against the current text of "{dirname}"')
def step_run_lint(context, dirname):
    assert dirname == context.lint_target, (dirname, context.lint_target)
    context.lint_result = run_rigging_command("lint", timeout=120)


@then('it exits 0')
def step_lint_exits_zero(context):
    assert context.lint_result.returncode == 0, (
        context.lint_result.stdout + context.lint_result.stderr
    )
