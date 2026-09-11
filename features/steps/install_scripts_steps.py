"""Step definitions for features/install-scripts.feature.

Each scenario runs the real packaging/install-*.sh script against real,
committed skills-core/schemas/templates/adapters content, redirected via
XDG_DATA_HOME, XDG_CONFIG_HOME, and HOME to disposable temp directories.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import os
from pathlib import Path

from behave import given, when, then

from support import REPO_ROOT, new_tmp_dir, run


def resolve_path(context, template):
    text = template
    text = text.replace("$XDG_DATA_HOME", str(context.xdg_data_home))
    text = text.replace("$HOME", str(context.home))
    if hasattr(context, "xdg_config_home"):
        text = text.replace("$XDG_CONFIG_HOME", str(context.xdg_config_home))
    return Path(text)


@given('XDG_DATA_HOME and HOME point at empty temporary directories')
def step_claude_env(context):
    context.xdg_data_home = new_tmp_dir(context, "pce-xdgdata-")
    context.home = new_tmp_dir(context, "pce-home-")


@given('XDG_DATA_HOME, XDG_CONFIG_HOME, and HOME point at empty temporary directories')
def step_opencode_env(context):
    context.xdg_data_home = new_tmp_dir(context, "pce-xdgdata-")
    context.xdg_config_home = new_tmp_dir(context, "pce-xdgconfig-")
    context.home = new_tmp_dir(context, "pce-home-")


@given('"$HOME/.claude/skills/critic" already exists with a stale file "{filename}"')
def step_stale_install(context, filename):
    context.xdg_data_home = new_tmp_dir(context, "pce-xdgdata-")
    context.home = new_tmp_dir(context, "pce-home-")
    stale_dir = context.home / ".claude" / "skills" / "critic"
    stale_dir.mkdir(parents=True)
    (stale_dir / filename).write_text("stale\n", encoding="utf-8")


@when('packaging/install-claude.sh runs')
def step_run_install_claude(context):
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = str(context.xdg_data_home)
    env["HOME"] = str(context.home)
    context.result = run(
        ["bash", str(REPO_ROOT / "packaging" / "install-claude.sh")], cwd=REPO_ROOT, env=env
    )
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr


@when('packaging/install-opencode.sh runs')
def step_run_install_opencode(context):
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = str(context.xdg_data_home)
    env["XDG_CONFIG_HOME"] = str(context.xdg_config_home)
    env["HOME"] = str(context.home)
    context.result = run(
        ["bash", str(REPO_ROOT / "packaging" / "install-opencode.sh")], cwd=REPO_ROOT, env=env
    )
    assert context.result.returncode == 0, context.result.stdout + context.result.stderr


@then('"{prefix_path}" contains skills-core, schemas, templates, and adapters')
def step_check_prefix_contents(context, prefix_path):
    resolved = resolve_path(context, prefix_path)
    for name in ("skills-core", "schemas", "templates", "adapters"):
        assert (resolved / name).is_dir(), f"{resolved}/{name} missing"


@then('"{skill_dir}" contains one directory per skill under adapters/{runtime}/skills')
def step_check_skill_dirs(context, skill_dir, runtime):
    resolved = resolve_path(context, skill_dir)
    expected = {p.name for p in (REPO_ROOT / "adapters" / runtime / "skills").iterdir() if p.is_dir()}
    actual = {p.name for p in resolved.iterdir() if p.is_dir()}
    assert expected == actual, f"expected {expected}, got {actual}"


@then('"{path}" no longer contains "{filename}"')
def step_no_longer_contains(context, path, filename):
    resolved = resolve_path(context, path)
    assert not (resolved / filename).exists()


@then('"{path}" matches adapters/{runtime}/skills/{name}/SKILL.md')
def step_matches_adapter(context, path, runtime, name):
    resolved = resolve_path(context, path)
    expected = (REPO_ROOT / "adapters" / runtime / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    actual = resolved.read_text(encoding="utf-8")
    assert actual == expected
