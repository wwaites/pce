"""Step definitions for features/run-loop.feature (non-sandbox scenarios).

Scenarios that only exercise parse_scope/to_glob/stage_workspace/collect_back
run the real packaging/run_loop.py copied into an isolated temp ROOT (so
SKILLS_CORE resolves inside the fixture, not the real project tree) via a
small in-process driver script. "Runner refuses a workflow directory with no
brief" runs the real committed script directly, since it never reaches
ROOT-dependent code before the brief.md check.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from behave import given, then, when
from support import REPO_ROOT, new_tmp_dir, run, validate_json_schema

IMPORT_PRELUDE = (
    "import importlib.util, json, sys\n"
    "from pathlib import Path\n"
    "spec = importlib.util.spec_from_file_location('run_loop', 'packaging/run_loop.py')\n"
    "run_loop = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(run_loop)\n"
)


def build_run_loop_fixture(context):
    tmp_root = new_tmp_dir(context, "pce-runloop-")
    (tmp_root / "packaging").mkdir()
    shutil.copy2(REPO_ROOT / "packaging" / "run_loop.py", tmp_root / "packaging" / "run_loop.py")
    (tmp_root / "skills-core").mkdir()
    shutil.copytree(REPO_ROOT / "schemas", tmp_root / "schemas")
    (tmp_root / "templates" / "reviews").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "templates" / "reviews" / "critic.md",
        tmp_root / "templates" / "reviews" / "critic.md",
    )
    return tmp_root


def run_driver(context, code):
    full = IMPORT_PRELUDE + code
    return run([sys.executable, "-c", full], cwd=context.tmp_root)


_MODULE_CACHE = {}


def _run_loop_module():
    """Load the real packaging/run_loop.py in-process, read-only.

    The accounting-record seam under test has no dependency on ROOT-relative
    resolution (SKILLS_CORE, templates), so it runs directly against the
    committed file rather than through the isolated-ROOT subprocess driver
    the other scenarios in this file need.
    """
    cached = _MODULE_CACHE.get("module")
    if cached is not None:
        return cached
    path = REPO_ROOT / "packaging" / "run_loop.py"
    spec = importlib.util.spec_from_file_location("run_loop_readonly", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _MODULE_CACHE["module"] = module
    return module


def _set_path(d, path, value):
    """Set a value in a nested dict from a dotted path string."""
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _build_canned_response(model_field, model, input_field, input_value, output_field, output_value, cost_field, cost_value):
    """Build a nested dict mimicking a real runtime's raw JSON response shape.

    A "<field> key" phrase, such as "modelUsage key", means the model name is
    the sole key of that field's object rather than a value at a path.
    """
    response = {}
    if model_field.endswith(" key"):
        container = model_field[: -len(" key")]
        response.setdefault(container, {})[model] = {}
    else:
        _set_path(response, model_field, model)
    _set_path(response, input_field, input_value)
    _set_path(response, output_field, output_value)
    _set_path(response, cost_field, cost_value)
    return response


def _find_accounting_record(workflow_dir, pass_id, role, runtime):
    history_dir = workflow_dir / "accounting" / "history"
    if not history_dir.is_dir():
        return []
    return [
        p for p in history_dir.glob("*")
        if p.is_file() and pass_id in p.name and role in p.name and runtime in p.name
    ]


# --- Runner refuses a workflow directory with no brief -------------------

@given("the PCE Nix package is installed")
def step_pce_package_installed(context):
    result = run(
        ["nix", "build", "path:.#default", "--no-link", "--print-out-paths"],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    context.pce_command = Path(result.stdout.strip()) / "bin" / "pce"


@given("packaging/run_loop.py in the source tree")
def step_source_runner(context):
    context.runner_paths = [REPO_ROOT / "packaging" / "run_loop.py"]


@given("run_loop.py installed under the PCE Nix package libexec directory")
def step_packaged_runner(context):
    result = run(
        ["nix", "build", "path:.#default", "--no-link", "--print-out-paths"],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    context.runner_paths.append(Path(result.stdout.strip()) / "libexec" / "run_loop.py")


@when("each bounded-pass runner resolves its runtime resources")
def step_resolve_runner_resources(context):
    context.runtime_roots = []
    for index, path in enumerate(context.runner_paths):
        spec = importlib.util.spec_from_file_location(f"run_loop_resources_{index}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        context.runtime_roots.append(module.ROOT)


@then('each runner finds the "author", "archivist", "fact-checker", and "critic" role skills')
def step_each_runner_finds_skills(context):
    roles = ("author", "archivist", "fact-checker", "critic")
    missing = [
        root / "skills-core" / f"{role}.md"
        for root in context.runtime_roots
        for role in roles
        if not (root / "skills-core" / f"{role}.md").is_file()
    ]
    assert not missing, missing


@then('each runner finds the "author", "archivist", "fact-checker", and "critic" task prompts')
def step_each_runner_finds_prompts(context):
    roles = ("author", "archivist", "fact-checker", "critic")
    missing = [
        root / "templates" / "prompts" / f"{role}-task.md"
        for root in context.runtime_roots
        for role in roles
        if not (root / "templates" / "prompts" / f"{role}-task.md").is_file()
    ]
    assert not missing, missing


@then('each runner finds the "claims.schema.json", "fact-check.schema.json", and "accounting.schema.json" schemas')
def step_each_runner_finds_schemas(context):
    schemas = ("claims.schema.json", "fact-check.schema.json", "accounting.schema.json")
    missing = [
        root / "schemas" / name
        for root in context.runtime_roots
        for name in schemas
        if not (root / "schemas" / name).is_file()
    ]
    assert not missing, missing


@then("each runner finds the critic review instructions")
def step_each_runner_finds_critic_review(context):
    missing = [
        root / "templates" / "reviews" / "critic.md"
        for root in context.runtime_roots
        if not (root / "templates" / "reviews" / "critic.md").is_file()
    ]
    assert not missing, missing


@given('a workflow directory with no "brief.md" file')
def step_workflow_no_brief(context):
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")


@when('the "pce" command runs against that directory with "--runtime {runtime}"')
def step_run_packaged_command(context, runtime):
    context.result = run(
        [str(context.pce_command), str(context.workflow_dir), "--runtime", runtime],
        cwd=REPO_ROOT,
    )


@when('the default flake app runs with "--help"')
def step_run_default_flake_app(context):
    context.result = run(["nix", "run", "path:.", "--", "--help"], cwd=REPO_ROOT)


@when('run_loop.py runs against that directory with "--runtime {runtime}"')
def step_run_main(context, runtime):
    context.result = run(
        [
            sys.executable,
            str(REPO_ROOT / "packaging" / "run_loop.py"),
            str(context.workflow_dir),
            "--runtime",
            runtime,
        ],
        cwd=REPO_ROOT,
    )


@then("it exits with status {code:d}")
def step_exit_status(context, code):
    assert context.result.returncode == code, context.result.stdout + context.result.stderr


@then('it reports that "{filename}" was not found')
def step_reports_not_found(context, filename):
    output = context.result.stdout + context.result.stderr
    assert filename in output and "not found" in output, output


@then("it reports the bounded review-pass runner help")
def step_reports_runner_help(context):
    output = context.result.stdout + context.result.stderr
    assert "Run one bounded artificial-organisation review pass" in output, output


# --- read-scope parsing ----------------------------------------------------

@given('skills-core/{source_name} has a "{heading}" section listing "{p1}" and "{p2}"')
def step_skill_scope_two(context, source_name, heading, p1, p2):
    context.tmp_root = build_run_loop_fixture(context)
    text = f"# Fixture\n\n{heading}\n\n- `{p1}`\n- `{p2}`\n"
    (context.tmp_root / "skills-core" / source_name).write_text(text, encoding="utf-8")


@when("run_loop.py parses the fact-checker read scope")
def step_parse_scope(context):
    code = "print(json.dumps(run_loop.parse_scope('fact-checker', '## Read Scope')))\n"
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.patterns = json.loads(context.result.stdout)


@then('it returns exactly the patterns "{p1}" and "{p2}"')
def step_check_patterns(context, p1, p2):
    assert context.patterns == [p1, p2], context.patterns


# --- staging ----------------------------------------------------------------

@given('a workflow directory containing "{p1}" and "{p2}"')
def step_workflow_with_files(context, p1, p2):
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")
    for rel in (p1, p2):
        path = context.workflow_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content of {rel}\n", encoding="utf-8")


@given('the fact-checker read scope names only "{pattern}"')
def step_fact_checker_scope_one(context, pattern):
    context.tmp_root = build_run_loop_fixture(context)
    text = f"# Fixture\n\n## Read Scope\n\n- `{pattern}`\n"
    (context.tmp_root / "skills-core" / "fact-checker.md").write_text(text, encoding="utf-8")


@when("run_loop.py stages a workspace for the fact-checker")
def step_stage_workspace(context):
    code = (
        "patterns = run_loop.parse_scope('fact-checker', '## Read Scope')\n"
        f"staged = run_loop.stage_workspace(Path(r'{context.workflow_dir}'), patterns)\n"
        "print(staged)\n"
    )
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.staged_dir = Path(context.result.stdout.strip())
    context.add_cleanup(shutil.rmtree, context.staged_dir, ignore_errors=True)


@then('the staged workspace contains "{relpath}"')
def step_staged_contains(context, relpath):
    assert (context.staged_dir / relpath).is_file(), list(context.staged_dir.rglob("*"))


@then('the staged workspace does not contain "{relpath}"')
def step_staged_not_contains(context, relpath):
    assert not (context.staged_dir / relpath).exists()


# --- collecting back ---------------------------------------------------------

@given('a staged workspace containing "{relpath}"')
def step_staged_workspace_with_file(context, relpath):
    context.staged_dir = new_tmp_dir(context, "pce-staged-")
    path = context.staged_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")


@given('the fact-checker write scope names "{pattern}"')
def step_fact_checker_write_scope(context, pattern):
    context.tmp_root = build_run_loop_fixture(context)
    text = f"# Fixture\n\n## Write Scope\n\n- `{pattern}`\n"
    (context.tmp_root / "skills-core" / "fact-checker.md").write_text(text, encoding="utf-8")


@when("run_loop.py collects the write scope back from the staged workspace")
def step_collect_back(context):
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")
    code = (
        "patterns = run_loop.parse_scope('fact-checker', '## Write Scope')\n"
        f"run_loop.collect_back(Path(r'{context.staged_dir}'), Path(r'{context.workflow_dir}'), patterns)\n"
    )
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr


@then('the workflow directory contains "{relpath}"')
def step_workflow_contains(context, relpath):
    assert (context.workflow_dir / relpath).is_file()


# --- glob resolution ----------------------------------------------------------

@given('the write-scope pattern "{pattern}"')
def step_scope_pattern(context, pattern):
    context.tmp_root = build_run_loop_fixture(context)
    context.pattern = pattern


@when('run_loop.py resolves it for pass id "{pass_id}"')
def step_resolve_glob(context, pass_id):
    code = f"print(run_loop.to_glob({context.pattern!r}, **{{'pass-id': {pass_id!r}}}))\n"
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.glob = context.result.stdout.strip()


@then('the resulting glob is "{expected}"')
def step_check_glob(context, expected):
    assert context.glob == expected, context.glob


# --- task-prompt template loading (Scenario Outline) ---------------------------

@given("templates/prompts/{role}-task.md exists with that role's task instructions")
def step_template_exists(context, role):
    context.tmp_root = build_run_loop_fixture(context)
    (context.tmp_root / "templates" / "prompts").mkdir(parents=True)
    content = f"Fixture task instructions for {role}.\n"
    (context.tmp_root / "templates" / "prompts" / f"{role}-task.md").write_text(content, encoding="utf-8")
    context.expected_prompt = content


@when('run_{role} in run_loop.py runs a real pass and reaches its call to dispatch()')
def step_run_role_reaches_dispatch(context, role):
    context.role = role
    func_name = "run_" + role.replace("-", "_")
    stub_skill = ""
    call_args = "'claude', workflow_dir"
    if role in ("fact-checker", "critic"):
        # run_fact_checker/run_critic read their scope from skills-core/{role}.md
        # before dispatching; a stub with no headings yields empty patterns.
        stub_skill = f"(Path('skills-core') / '{role}.md').write_text('# stub\\n', encoding='utf-8')\n"
    if role == "critic":
        call_args += ", 'reviewer', 'General clarity and factual grounding review.'"
    code = (
        "import tempfile\n"
        "from pathlib import Path\n"
        f"{stub_skill}"
        "workflow_dir = Path(tempfile.mkdtemp(prefix='pce-workflow-'))\n"
        "captured = {}\n"
        "class _Captured(Exception):\n"
        "    pass\n"
        "def _fake_dispatch(runtime, role_arg, task, cwd, model=None):\n"
        "    # @exceptional-double: dispatch()'s real CLI subprocess call is\n"
        "    # covered for real by the @sandbox tier scenario; this fake\n"
        "    # captures the composition, the task argument passed in, only.\n"
        "    captured['task'] = task\n"
        "    raise _Captured()\n"
        "run_loop.dispatch = _fake_dispatch\n"
        "try:\n"
        f"    run_loop.{func_name}({call_args})\n"
        "except _Captured:\n"
        "    pass\n"
        "print(captured['task'], end='')\n"
    )
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.captured_task = context.result.stdout


@then('the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md')
def step_check_task_starts_with_template(context, role):
    assert context.captured_task.startswith(context.expected_prompt), context.captured_task


@then("run_loop.py contains no hardcoded English sentence as that role's task text")
def step_no_hardcoded_task_text(context):
    func_name = "run_" + context.role.replace("-", "_")
    source = (REPO_ROOT / "packaging" / "run_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func_name),
        None,
    )
    assert func is not None, f"{func_name} not found in packaging/run_loop.py"
    calls_build_dispatch_task = False
    hardcoded = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "task" for target in node.targets
        ):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "build_dispatch_task":
                    calls_build_dispatch_task = True
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and len(sub.value.split()) > 4:
                    hardcoded.append(sub.value)
    assert calls_build_dispatch_task, f"{func_name} does not build its task from build_dispatch_task()"
    assert not hardcoded, f"{func_name} still hardcodes task prose: {hardcoded}"


# --- accounting record -------------------------------------------------------

@given("a successful OpenCode role dispatch whose session export is {size:d} bytes of valid JSON")
def step_opencode_export_size(context, size):
    context.export_size = size
    context.export_limit = None


@given("a successful OpenCode role dispatch whose session export exceeds a {limit:d} byte export capture ceiling")
def step_opencode_export_exceeds_limit(context, limit):
    context.export_size = limit + 1
    context.export_limit = limit


def _run_export_capture(context, limit):
    context.tmp_root = build_run_loop_fixture(context)
    (context.tmp_root / "skills-core" / "author.md").write_text("# Author fixture\n", encoding="utf-8")
    context.evidence_path = context.tmp_root / "session-export.json"
    payload = json.dumps({"info": {"model": {"id": "fixture-model"}}})
    payload = payload[:-1] + ',"padding":"' + "x" * (context.export_size - len(payload) - 13) + '"}'
    payload_path = context.tmp_root / "export-fixture.json"
    payload_path.write_text(payload, encoding="utf-8")
    code = (
        "class _Result:\n"
        "    returncode = 0\n"
        "    stderr = ''\n"
        "calls = 0\n"
        "def _run(cmd, **kwargs):\n"
        "    global calls\n"
        "    calls += 1\n"
        "    result = _Result()\n"
        "    result.stdout = " + repr('{"sessionID":"fixture","part":{"tokens":{"input":1,"output":1},"cost":0}}') + f" if calls == 1 else Path(r'{payload_path}').read_text(encoding='utf-8')\n"
        "    return result\n"
        "run_loop.subprocess.run = _run\n"
        "try:\n"
        f"    run_loop.run_opencode('# fixture', 'task', Path('.'), export_capture_limit={limit}, export_evidence_path=Path(r'{context.evidence_path}'))\n"
        "except Exception:\n"
        "    import traceback\n"
        "    traceback.print_exc()\n"
        "    raise\n"
    )
    context.result = run_driver(context, code)


@when("run_loop.py captures the session export with the default export capture ceiling")
def step_capture_default_limit(context):
    _run_export_capture(context, None)


@when('run_loop.py captures the session export with "--export-capture-limit {limit:d}"')
def step_capture_explicit_limit(context, limit):
    _run_export_capture(context, limit)


@when('the "pce" command captures the session export with "--export-capture-limit {limit:d}"')
def step_packaged_capture_explicit_limit(context, limit):
    _run_export_capture(context, limit)


@then("it parses the complete session export for accounting")
def step_complete_export_parsed(context):
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr


@then("it preserves the complete session export as raw evidence")
@then("it preserves the captured session export as raw evidence")
def step_export_evidence_preserved(context):
    assert context.evidence_path.is_file(), context.result.stdout + context.result.stderr
    assert context.evidence_path.stat().st_size == context.export_size


@then("it exits with status 2 before parsing the partial session export")
def step_partial_export_rejected(context):
    assert context.result.returncode == 2, context.result.stdout + context.result.stderr
    assert "JSONDecodeError" not in context.result.stderr, context.result.stderr


@then("the failure reports the configured ceiling as {limit:d} bytes")
def step_failure_reports_ceiling(context, limit):
    assert str(limit) in context.result.stderr, context.result.stderr


@then("the failure reports the observed export size when it is known")
def step_failure_reports_observed_size(context):
    assert str(context.export_size) in context.result.stderr, context.result.stderr


@then('it reports "--export-capture-limit" with a default of {limit:d} bytes')
def step_help_reports_export_capture_limit(context, limit):
    output = context.result.stdout + context.result.stderr
    assert f"--export-capture-limit" in output, output
    assert f"(default: {limit})" in " ".join(output.split()), output

@given('run_loop.py dispatches the "{role}" role in pass "{pass_id}" through the "{runtime}" runtime')
def step_accounting_dispatch_setup(context, role, pass_id, runtime):
    context.workflow_dir = new_tmp_dir(context, "pce-accounting-")
    context.role = role
    context.pass_id = pass_id
    context.runtime = runtime


@given(
    'that runtime\'s response reports "{model_field}" "{model}", "{input_field}" {input_value:d}, '
    '"{output_field}" {output_value:d}, and "{cost_field}" {cost_value:g}'
)
def step_accounting_response(
    context, model_field, model, input_field, input_value, output_field, output_value, cost_field, cost_value
):
    response = _build_canned_response(
        model_field, model, input_field, input_value, output_field, output_value, cost_field, cost_value
    )
    context.response_text = json.dumps(response)


@when("that dispatch completes")
def step_dispatch_completes(context):
    run_loop = _run_loop_module()
    run_loop.write_accounting_record(
        context.workflow_dir, context.pass_id, context.role, context.runtime, context.response_text
    )


@then(
    'the workflow directory contains an accounting record under "accounting/history/" naming pass '
    '"{pass_id}", role "{role}", and runtime "{runtime}"'
)
def step_accounting_record_exists(context, pass_id, role, runtime):
    matches = _find_accounting_record(context.workflow_dir, pass_id, role, runtime)
    assert len(matches) == 1, (matches, list((context.workflow_dir / "accounting" / "history").glob("*")))
    context.accounting_record = json.loads(matches[0].read_text(encoding="utf-8"))


@then('that record\'s model is "{model}"')
def step_record_model(context, model):
    assert context.accounting_record.get("model") == model, context.accounting_record


@then("that record's input_tokens is {value:d}")
def step_record_input_tokens(context, value):
    assert context.accounting_record.get("input_tokens") == value, context.accounting_record


@then("that record's output_tokens is {value:d}")
def step_record_output_tokens(context, value):
    assert context.accounting_record.get("output_tokens") == value, context.accounting_record


@then("that record's cost_usd is {value:g}")
def step_record_cost_usd(context, value):
    assert context.accounting_record.get("cost_usd") == value, context.accounting_record


# --- accounting record schema conformance -------------------------------------

@given("an accounting record written for a role dispatch")
def step_accounting_record_written(context):
    context.workflow_dir = new_tmp_dir(context, "pce-accounting-")
    response = _build_canned_response(
        "modelUsage key", "claude-sonnet-5",
        "usage.input_tokens", 2,
        "usage.output_tokens", 4,
        "total_cost_usd", 0.0388,
    )
    run_loop = _run_loop_module()
    run_loop.write_accounting_record(context.workflow_dir, "pass1", "author", "claude", json.dumps(response))
    matches = _find_accounting_record(context.workflow_dir, "pass1", "author", "claude")
    assert len(matches) == 1, matches
    context.accounting_record = json.loads(matches[0].read_text(encoding="utf-8"))


@when('the record is checked against the "Accounting Record" schema')
def step_check_record_schema(context):
    schema = json.loads((REPO_ROOT / "schemas" / "accounting.schema.json").read_text(encoding="utf-8"))
    context.schema_errors = validate_json_schema(context.accounting_record, schema)


@then('the response conforms to the "Accounting Record" schema in "schemas/accounting.schema.json"')
def step_record_conforms(context):
    assert not context.schema_errors, context.schema_errors


# --- stable completion interface ----------------------------------------------

@given('a bounded pass whose required gates return "{fact_verdict}" and "{critic_verdict}"')
def step_bounded_pass_verdicts(context, fact_verdict, critic_verdict):
    context.fact_verdict = fact_verdict
    context.critic_verdict = critic_verdict
    context.runtime_fails = False


@given('a bounded pass whose required critic gate returns "{critic_verdict}"')
def step_bounded_pass_critic_verdict(context, critic_verdict):
    context.fact_verdict = "pass"
    context.critic_verdict = critic_verdict
    context.runtime_fails = False


@given("a bounded pass whose required gate runtime fails")
def step_bounded_pass_runtime_failure(context):
    context.fact_verdict = "pass"
    context.critic_verdict = "approve"
    context.runtime_fails = True


def _run_bounded_pass_fixture(context):
    workflow_dir = new_tmp_dir(context, "pce-outcome-")
    (workflow_dir / "brief.md").write_text("# Fixture brief\n", encoding="utf-8")
    (workflow_dir / "state.json").write_text(json.dumps({
        "required_gates": ["fact-checker", "critic"],
        "critic_profiles": {"reviewer": {"remit": "Fixture remit."}},
    }), encoding="utf-8")
    code = IMPORT_PRELUDE + (
        "# @exceptional-double: real role dispatch is covered by the @sandbox tier; "
        "this fixture isolates main() completion composition.\n"
        "run_loop.run_author = lambda runtime, workflow_dir: None\n"
        "run_loop.run_archivist = lambda runtime, workflow_dir: None\n"
        f"run_loop.run_fact_checker = lambda runtime, workflow_dir: {{'verdict': {context.fact_verdict!r}}}\n"
        f"run_loop.run_critic = lambda runtime, workflow_dir, profile_id, remit: "
        f"{{'verdict': {context.critic_verdict!r}}}\n"
    )
    if context.runtime_fails:
        code += "run_loop.run_fact_checker = lambda runtime, workflow_dir: (_ for _ in ()).throw(RuntimeError('fixture failure'))\n"
    code += (
        f"sys.argv = ['run_loop.py', {str(workflow_dir)!r}, '--runtime', 'pi']\n"
        "raise SystemExit(run_loop.main())\n"
    )
    context.result = run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
    )


@when("run_loop.py completes the pass")
def step_complete_bounded_pass(context):
    _run_bounded_pass_fixture(context)


@when("run_loop.py stops the pass")
def step_stop_bounded_pass(context):
    _run_bounded_pass_fixture(context)


@then('it emits one JSON completion summary with completion_state "{state}"')
def step_json_completion_state(context, state):
    summaries = [json.loads(line) for line in context.result.stdout.splitlines() if line.startswith("{")]
    assert len(summaries) == 1, context.result.stdout + context.result.stderr
    assert summaries[0]["completion_state"] == state, summaries[0]
    context.completion_summary = summaries[0]


@then('the summary lists the ordered gate verdicts "{fact_verdict}" and "{critic_verdict}"')
def step_json_ordered_verdicts(context, fact_verdict, critic_verdict):
    assert context.completion_summary["gate_verdicts"] == [fact_verdict, critic_verdict], context.completion_summary


# --- model pinning ------------------------------------------------------------

def _pending_state(context):
    if not hasattr(context, "pending_state"):
        context.pending_state = {}
    return context.pending_state


def _fake_subprocess_driver_code(call_line):
    """Driver body that fakes subprocess.run to capture the built command line,
    calls the given real run_loop call, and prints the captured command.

    The real function under test still runs end to end up to the subprocess
    boundary; only the external CLI process itself, which the @sandbox tier
    covers for real, is stood in for here.
    """
    return (
        "class _FakeResult:\n"
        "    def __init__(self):\n"
        "        self.returncode = 0\n"
        "        self.stdout = '{}'\n"
        "        self.stderr = ''\n"
        "captured = {}\n"
        "def _fake_run(cmd, **kwargs):\n"
        "    captured['cmd'] = cmd\n"
        "    return _FakeResult()\n"
        "run_loop.subprocess.run = _fake_run\n"
        "try:\n"
        f"    {call_line}\n"
        "except Exception:\n"
        "    pass\n"
        "print(json.dumps(captured.get('cmd')))\n"
    )


@given("a role dispatch whose runtime exits non-zero with empty stderr")
def step_failed_dispatch(context):
    context.tmp_root = build_run_loop_fixture(context)
    context.failed_role = "critic"
    context.failed_runtime = "opencode"
    context.failed_status = 17
    (context.tmp_root / "skills-core" / "critic.md").write_text("# Critic fixture\n", encoding="utf-8")


@given("the runtime writes output and structured events to stdout")
def step_failed_dispatch_stdout(context):
    context.failed_stdout = 'critic output\n{"type":"error","message":"provider rejected request"}'


@when("run_loop.py reports the dispatch failure")
def step_report_dispatch_failure(context):
    code = (
        "class _FailedResult:\n"
        f"    returncode = {context.failed_status}\n"
        f"    stdout = {context.failed_stdout!r}\n"
        "    stderr = ''\n"
        "def _failed_run(cmd, **kwargs):\n"
        "    # @exceptional-double: real runtimes cannot reliably produce this\n"
        "    # specific non-zero, empty-stderr condition on demand.\n"
        "    return _FailedResult()\n"
        "run_loop.subprocess.run = _failed_run\n"
        "try:\n"
        "    run_loop.run_opencode('# Critic fixture', 'fixture task', Path('.'))\n"
        "except RuntimeError as exc:\n"
        f"    print({context.failed_role!r} + ': ' + str(exc))\n"
    )
    context.result = run_driver(context, code)
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.failure = context.result.stdout


@then("the failure names the role, runtime, and exit status")
def step_failure_identity(context):
    assert context.failed_role in context.failure, context.failure
    assert context.failed_runtime in context.failure, context.failure
    assert str(context.failed_status) in context.failure, context.failure


@then("the failure includes the captured stdout and structured events")
def step_failure_evidence(context):
    assert context.failed_stdout in context.failure, context.failure


@given('a workflow directory with state.json\'s "models.{role}" naming model "{model}" for runtime "{runtime}"')
def step_model_pin_role_setup(context, role, model, runtime):
    state = _pending_state(context)
    state.setdefault("models", {}).setdefault(role, {})[runtime] = model


@given('state.json\'s "models.{role}" names model "{model}" for runtime "{runtime}"')
def step_model_pin_named(context, role, model, runtime):
    state = _pending_state(context)
    state.setdefault("models", {}).setdefault(role, {})[runtime] = model


@given('critic profile "{profile}" names model "{model}" for runtime "{runtime}"')
def step_critic_profile_model(context, profile, model, runtime):
    state = _pending_state(context)
    state.setdefault("critic_profiles", {}).setdefault(profile, {"remit": "Fixture remit."})
    state["critic_profiles"][profile].setdefault("model", {})[runtime] = model


@given('critic profile "{profile}" names a model only for runtime "{runtime}"')
def step_critic_profile_model_only(context, profile, runtime):
    state = _pending_state(context)
    state.setdefault("critic_profiles", {}).setdefault(profile, {"remit": "Fixture remit."})
    state["critic_profiles"][profile].setdefault("model", {})[runtime] = "opus"


@when('run_loop.py dispatches the "{role}" role through the "{runtime}" runtime')
def step_dispatch_role_for_model(context, role, runtime):
    context.tmp_root = build_run_loop_fixture(context)
    (context.tmp_root / "templates" / "prompts").mkdir(parents=True, exist_ok=True)
    (context.tmp_root / "templates" / "prompts" / f"{role}-task.md").write_text(
        f"Fixture task for {role}.\n", encoding="utf-8"
    )
    (context.tmp_root / "skills-core" / f"{role}.md").write_text("# stub\n", encoding="utf-8")
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")
    state = _pending_state(context)
    (context.workflow_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    func_name = "run_" + role.replace("-", "_")
    call_line = f"run_loop.{func_name}({runtime!r}, Path(r'{context.workflow_dir}'))"
    context.result = run_driver(context, _fake_subprocess_driver_code(call_line))
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.dispatched_cmd = json.loads(context.result.stdout.strip().splitlines()[-1])


@when('run_loop.py dispatches the "{profile}" critic profile through the "{runtime}" runtime')
def step_dispatch_critic_profile_for_model(context, profile, runtime):
    context.tmp_root = build_run_loop_fixture(context)
    (context.tmp_root / "templates" / "prompts").mkdir(parents=True, exist_ok=True)
    (context.tmp_root / "templates" / "prompts" / "critic-task.md").write_text(
        "Fixture task for critic.\n", encoding="utf-8"
    )
    (context.tmp_root / "skills-core" / "critic.md").write_text("# stub\n", encoding="utf-8")
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")
    state = _pending_state(context)
    (context.workflow_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    remit = state.get("critic_profiles", {}).get(profile, {}).get("remit", "Fixture remit.")
    call_line = (
        f"run_loop.run_critic({runtime!r}, Path(r'{context.workflow_dir}'), {profile!r}, {remit!r})"
    )
    context.result = run_driver(context, _fake_subprocess_driver_code(call_line))
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr
    context.dispatched_cmd = json.loads(context.result.stdout.strip().splitlines()[-1])


@then('the dispatched subprocess command includes "--model" followed by "{model}"')
def step_cmd_includes_model(context, model):
    cmd = context.dispatched_cmd
    assert cmd is not None, "no subprocess command captured"
    assert "--model" in cmd, cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == model, cmd


@then('the dispatched subprocess command does not include "--model"')
def step_cmd_excludes_model(context):
    cmd = context.dispatched_cmd
    assert cmd is not None, "no subprocess command captured"
    assert "--model" not in cmd, cmd


# --- real bounded pass (@sandbox) ------------------------------------------

SANDBOX_BRIEF = (
    "# Brief\n\n"
    "- Task: Write exactly one sentence stating the founding year of the fictional "
    "town of Elmshire, citing the source document by filename.\n"
    "- Audience: internal reviewers\n"
    "- Scope: one sentence\n"
    "- Acceptance bar: the sentence must be fully supported by sources/external/doc-a.md "
    "and must not add any fact doc-a.md does not state\n"
    "- Risk level: low\n"
    "- Specialist questions: none\n"
    "- Output shape: exactly one sentence\n"
)

SANDBOX_SOURCE = (
    "# Elmshire Town Record\n\n"
    "Elmshire was founded in the year 1842 by a group of settlers from the river valley.\n"
)


@given('a workflow directory with "brief.md", "state.json" naming the "{gate1}" and "{gate2}" gates, and an approved source pack')
def step_sandbox_workflow(context, gate1, gate2):
    context.workflow_dir = new_tmp_dir(context, "pce-sandbox-")
    (context.workflow_dir / "brief.md").write_text(SANDBOX_BRIEF, encoding="utf-8")
    state = {
        "risk": "low",
        "max_passes": 1,
        "required_gates": [gate1, gate2],
        "critic_score_policy": "advisory-only",
        "acceptance_policy": "editor judgement from concrete findings",
        "critic_profiles": {"reviewer": {"remit": "General clarity and factual grounding review."}},
        "specialist_questions": {},
    }
    (context.workflow_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    sources_dir = context.workflow_dir / "sources" / "external"
    sources_dir.mkdir(parents=True)
    (sources_dir / "doc-a.md").write_text(SANDBOX_SOURCE, encoding="utf-8")


@then('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
def step_check_dispatch_order(context):
    output = context.result.stdout + context.result.stderr
    author_at = output.find("== author ==")
    archivist_at = output.find("== archivist ==")
    fact_checker_gate_at = output.find("== gate: fact-checker ==")
    critic_gate_at = output.find("== gate: critic ==")
    assert -1 not in (author_at, archivist_at, fact_checker_gate_at, critic_gate_at), output
    assert author_at < archivist_at < fact_checker_gate_at < critic_gate_at, output


@then('the packaged pass dispatches "author", "archivist", "fact-checker", and "critic" through the real OpenCode runtime in order')
def step_check_packaged_dispatch_order(context):
    step_check_dispatch_order(context)


@then("the workflow directory contains one normalized accounting record for each successful role dispatch in that order")
def step_check_packaged_accounting_records(context):
    history_dir = context.workflow_dir / "accounting" / "history"
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in history_dir.glob("*.json")
    ]
    records.sort(key=lambda record: record["timestamp"])
    assert [record["role"] for record in records] == [
        "author", "archivist", "fact-checker", "critic"
    ], records
    assert all(record["runtime"] == "opencode" for record in records), records


@then('the critic accounting record names profile "{profile}"')
def step_check_critic_accounting_profile(context, profile):
    history_dir = context.workflow_dir / "accounting" / "history"
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in history_dir.glob("*.json")
    ]
    critic_records = [record for record in records if record["role"] == "critic"]
    assert len(critic_records) == 1, records
    assert critic_records[0]["profile_id"] == profile, critic_records[0]


@then("it prints the fact-checker verdict and the critic verdict in its summary")
@then("the packaged pass reports the fact-checker and critic verdicts")
def step_check_verdict_printed(context):
    output = context.result.stdout + context.result.stderr
    summary = output.split("== summary ==", 1)[-1]
    assert "fact-checker:" in summary, output
    assert any(line.startswith("critic:") for line in summary.splitlines()), output


@then('it exits 0 only when every verdict is "pass" or "approve"')
@then('the packaged pass exits 0 only when every verdict is "pass" or "approve"')
def step_check_exit_matches_verdicts(context):
    output = context.result.stdout + context.result.stderr
    summary = output.split("== summary ==", 1)[-1]
    verdict_lines = [
        line
        for line in summary.splitlines()
        if line.startswith(("fact-checker:", "critic:"))
    ]
    all_ok = all(line.rsplit(":", 1)[1].strip() in ("pass", "approve") for line in verdict_lines)
    expected_code = 0 if all_ok else 1
    assert context.result.returncode == expected_code, (
        f"verdicts={verdict_lines!r} exit={context.result.returncode!r} expected={expected_code!r}"
    )
