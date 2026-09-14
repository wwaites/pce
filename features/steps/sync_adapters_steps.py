"""Step definitions for features/sync-adapters.feature.

Each scenario runs the real packaging/sync-adapters.py against an isolated
copy of skills-core/ and adapters/, so runs are real and namespaced without
mutating the tracked repository tree.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys

from behave import given, when, then

from support import REPO_ROOT, new_tmp_dir, run

_MODULE_CACHE = {}


def _sync_adapters_module():
    """Load the real sync-adapters.py module, read-only, to look up its SKILLS map."""
    cached = _MODULE_CACHE.get("module")
    if cached is not None:
        return cached
    path = REPO_ROOT / "packaging" / "sync-adapters.py"
    spec = importlib.util.spec_from_file_location("sync_adapters_readonly", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _MODULE_CACHE["module"] = module
    return module


def build_fixture(context):
    tmp_root = new_tmp_dir(context, "pce-sync-")
    (tmp_root / "packaging").mkdir()
    shutil.copy2(REPO_ROOT / "packaging" / "sync-adapters.py", tmp_root / "packaging" / "sync-adapters.py")
    shutil.copytree(REPO_ROOT / "skills-core", tmp_root / "skills-core")
    shutil.copytree(REPO_ROOT / "adapters", tmp_root / "adapters")
    return tmp_root


@given('adapters/{runtime}/skills/{name}/SKILL.md does not exist')
def step_missing_adapter(context, runtime, name):
    context.tmp_root = build_fixture(context)
    target = context.tmp_root / "adapters" / runtime / "skills" / name / "SKILL.md"
    target.unlink()


@given('skills-core/{source_name} no longer contains "{phrase}"')
def step_remove_policy_phrase(context, source_name, phrase):
    context.tmp_root = build_fixture(context)
    path = context.tmp_root / "skills-core" / source_name
    text = path.read_text(encoding="utf-8")
    assert phrase in text, f"fixture setup expected {phrase!r} in {source_name}"
    path.write_text(text.replace(phrase, ""), encoding="utf-8")


@given('skills-core/{source_name} contains the word "{word}"')
def step_add_forbidden_word(context, source_name, word):
    context.tmp_root = build_fixture(context)
    path = context.tmp_root / "skills-core" / source_name
    path.write_text(path.read_text(encoding="utf-8") + f"\n{word}\n", encoding="utf-8")


@given('adapters/{runtime}/skills/{name}/SKILL.md differs from the text sync-adapters.py would generate')
def step_drift_adapter(context, runtime, name):
    context.tmp_root = build_fixture(context)
    path = context.tmp_root / "adapters" / runtime / "skills" / name / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nstale hand-edit\n", encoding="utf-8")


@given('the plugin-root copy of skills/{name}/SKILL.md does not exist')
def step_missing_plugin_root_skill(context, name):
    context.tmp_root = build_fixture(context)
    target = context.tmp_root / "skills" / name / "SKILL.md"
    if target.exists():
        target.unlink()


@given('the plugin-root copy of skills/{name}/SKILL.md differs from the text sync-adapters.py would generate')
def step_drift_plugin_root_skill(context, name):
    context.tmp_root = build_fixture(context)
    claude_copy = context.tmp_root / "adapters" / "claude" / "skills" / name / "SKILL.md"
    target = context.tmp_root / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(claude_copy.read_text(encoding="utf-8") + "\nstale hand-edit\n", encoding="utf-8")


@given('adapters/{runtime}/skills/{name}/ contains an extra file "{filename}"')
def step_extra_file(context, runtime, name, filename):
    context.tmp_root = build_fixture(context)
    path = context.tmp_root / "adapters" / runtime / "skills" / name / filename
    path.write_text("stray\n", encoding="utf-8")


@when('sync-adapters.py runs without "--check"')
def step_run_sync(context):
    _run_sync(context, check=False)


@when('sync-adapters.py runs with "--check"')
def step_run_sync_check(context):
    _run_sync(context, check=True)


def _run_sync(context, check):
    script = context.tmp_root / "packaging" / "sync-adapters.py"
    cmd = [sys.executable, str(script)]
    if check:
        cmd.append("--check")
    context.result = run(cmd, cwd=context.tmp_root)


@then('adapters/{runtime}/skills/{name}/SKILL.md is written')
def step_check_written(context, runtime, name):
    path = context.tmp_root / "adapters" / runtime / "skills" / name / "SKILL.md"
    assert path.is_file(), (
        f"expected {path} to be written; "
        f"stdout={context.result.stdout} stderr={context.result.stderr}"
    )
    context.written_path = path


@then('skills/{name}/SKILL.md is written')
def step_check_plugin_root_written(context, name):
    path = context.tmp_root / "skills" / name / "SKILL.md"
    assert path.is_file(), (
        f"expected {path} to be written; "
        f"stdout={context.result.stdout} stderr={context.result.stderr}"
    )
    context.written_path = path


@then('its frontmatter carries "{name_field}" and the {role} description')
def step_check_frontmatter(context, name_field, role):
    text = context.written_path.read_text(encoding="utf-8")
    assert name_field in text, text
    module = _sync_adapters_module()
    _source_name, description = module.SKILLS[role]
    assert description in text, text


@then('its body is the current text of skills-core/{source_name}')
def step_check_body(context, source_name):
    text = context.written_path.read_text(encoding="utf-8")
    opening, separator, remainder = text.partition("\n---\n")
    assert separator, text
    assert remainder.startswith("\n"), remainder
    body = remainder[1:]
    expected = (context.tmp_root / "skills-core" / source_name).read_text(encoding="utf-8")
    assert body == expected


@then('the check exits non-zero')
def step_check_nonzero(context):
    assert context.result.returncode != 0, context.result.stdout + context.result.stderr


@then('it names the missing policy phrase for "{source_path}"')
def step_names_missing_policy(context, source_path):
    output = context.result.stdout + context.result.stderr
    assert source_path in output, output
    assert "missing policy" in output, output


@then('it names the forbidden pattern found in "{source_path}"')
def step_names_forbidden(context, source_path):
    output = context.result.stdout + context.result.stderr
    assert source_path in output, output
    assert "forbidden policy pattern" in output, output


@then('it reports "{message}" for "{location}"')
def step_reports_message(context, message, location):
    output = context.result.stdout + context.result.stderr
    assert f"{location}: {message}" in output, output


@then('it prints a unified diff between the existing file and the expected text')
def step_prints_diff(context):
    output = context.result.stdout + context.result.stderr
    assert "---" in output and "+++" in output and "@@" in output, output


@then('it names "{filename}" as an unexpected file under "{location}"')
def step_names_unexpected(context, filename, location):
    output = context.result.stdout + context.result.stderr
    assert location in output, output
    assert filename in output, output
