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
import json
import os
import shutil
import sys
from pathlib import Path

from behave import given, when, then

from support import REPO_ROOT, new_tmp_dir, run

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


# --- Runner refuses a workflow directory with no brief -------------------

@given('a workflow directory with no "brief.md" file')
def step_workflow_no_brief(context):
    context.workflow_dir = new_tmp_dir(context, "pce-workflow-")


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
        "def _fake_dispatch(runtime, role_arg, task, cwd):\n"
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


@when("run_loop.py runs against that directory with a real agent runtime")
def step_run_real_pass(context):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    context.result = run(
        [sys.executable, str(REPO_ROOT / "packaging" / "run_loop.py"), str(context.workflow_dir), "--runtime", "claude"],
        cwd=REPO_ROOT,
        env=env,
        timeout=1800,
    )


@then('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
def step_check_dispatch_order(context):
    output = context.result.stdout + context.result.stderr
    author_at = output.find("== author ==")
    archivist_at = output.find("== archivist ==")
    fact_checker_gate_at = output.find("== gate: fact-checker ==")
    critic_gate_at = output.find("== gate: critic ==")
    assert -1 not in (author_at, archivist_at, fact_checker_gate_at, critic_gate_at), output
    assert author_at < archivist_at < fact_checker_gate_at < critic_gate_at, output


@then("it prints the fact-checker verdict and the critic verdict in its summary")
def step_check_verdict_printed(context):
    output = context.result.stdout + context.result.stderr
    summary = output.split("== summary ==", 1)[-1]
    assert "fact-checker:" in summary, output
    assert any(line.startswith("critic:") for line in summary.splitlines()), output


@then('it exits 0 only when every verdict is "pass" or "approve"')
def step_check_exit_matches_verdicts(context):
    output = context.result.stdout + context.result.stderr
    summary = output.split("== summary ==", 1)[-1]
    verdict_lines = [line for line in summary.splitlines() if ":" in line]
    all_ok = all(line.rsplit(":", 1)[1].strip() in ("pass", "approve") for line in verdict_lines)
    expected_code = 0 if all_ok else 1
    assert context.result.returncode == expected_code, (
        f"verdicts={verdict_lines!r} exit={context.result.returncode!r} expected={expected_code!r}"
    )
