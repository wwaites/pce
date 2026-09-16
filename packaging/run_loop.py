#!/usr/bin/env python3
"""Run one bounded artificial-organisation review pass against a real workflow directory.

This is the tiny runner from README's Next Steps: author -> archivist -> each
configured gate in state.json, once each, no auto-revision retry loop. It
dispatches each role as a real subprocess of the chosen runtime (claude or
opencode), and stages a scratch workspace for reviewer roles containing only
the files their Read Scope in skills-core/<role>.md names, so a reviewer's own
file-read tool cannot reach sources/internal/** or prior reviews even though
this script grants it ordinary file tools.
"""

from __future__ import annotations

import argparse
import glob as globmod
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_CORE = ROOT / "skills-core"
PASS_ID = "pass1"
TIMEOUT_SECONDS = 600


def parse_scope(role: str, heading: str) -> list[str]:
    """Extract backtick-quoted path patterns from a role's Read Scope or Write Scope section.

    @planks('it returns exactly the patterns "{p1}" and "{p2}"')
    """
    text = (SKILLS_CORE / f"{role}.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading) + 1
    except StopIteration:
        return []
    patterns = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        patterns.extend(re.findall(r"`([^`]+)`", line))
    return patterns


def substitute(pattern: str, **placeholders: str) -> str:
    """Replace each named placeholder with its value.

    @planks('the resulting glob is "{expected}"')
    """
    for key, value in placeholders.items():
        pattern = pattern.replace(f"<{key}>", value)
    return pattern


def to_glob(pattern: str, **placeholders: str) -> str:
    """Substitute known placeholders, then turn any remaining <...> token into a glob wildcard.

    @planks('the resulting glob is "{expected}"')
    """
    return re.sub(r"<[^>]+>", "*", substitute(pattern, **placeholders))


def stage_workspace(workflow_dir: Path, patterns: list[str]) -> Path:
    """Copy every file matching a read-scope pattern into a fresh scratch directory.

    @planks('the staged workspace does not contain "{relpath}"')
    """
    staged = Path(tempfile.mkdtemp(prefix="pce-stage-"))
    for pattern in patterns:
        matches = globmod.glob(pattern, root_dir=workflow_dir, recursive=True)
        if not matches and (workflow_dir / pattern).is_file():
            matches = [pattern]
        for rel in matches:
            src = workflow_dir / rel
            if not src.is_file():
                continue
            dest = staged / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    (staged / "reviews" / "history").mkdir(parents=True, exist_ok=True)
    (staged / "reviews" / "current").mkdir(parents=True, exist_ok=True)
    return staged


def collect_back(staged: Path, workflow_dir: Path, patterns: list[str]) -> list[Path]:
    """Copy every file matching a write-scope pattern back from the scratch directory.

    @planks('the workflow directory contains "{relpath}"')
    """
    written = []
    for pattern in patterns:
        matches = globmod.glob(pattern, root_dir=staged, recursive=True)
        for rel in matches:
            src = staged / rel
            if not src.is_file():
                continue
            dest = workflow_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            written.append(dest)
    return written


def run_claude(system_prompt: str, message: str, cwd: Path, model: str | None = None) -> str:
    """Run one bounded claude CLI turn with the given system prompt and task.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks('the dispatched subprocess command includes "--model" followed by "{model}"')
    @planks('the dispatched subprocess command does not include "--model"')
    """
    cmd = [
        "claude", "-p", message,
        "--append-system-prompt", system_prompt,
        "--tools", "Read,Write,Edit,Glob",
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--output-format", "json",
    ]
    if model is not None:
        cmd.extend(["--model", model])
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def run_opencode(system_prompt: str, message: str, cwd: Path, model: str | None = None) -> str:
    """Run one bounded opencode CLI turn with the given system prompt and task.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks('the dispatched subprocess command includes "--model" followed by "{model}"')
    @planks('the dispatched subprocess command does not include "--model"')
    """
    combined = f"{system_prompt}\n\n---\n\nTask:\n\n{message}"
    cmd = ["opencode", "run", combined, "--dir", str(cwd), "--format", "json"]
    if model is not None:
        cmd.extend(["--model", model])
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencode exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def run_pi(role: str, skill_path: Path, message: str, cwd: Path, model: str | None = None) -> str:
    """Run one bounded pi CLI turn, loading the role's skill file via pi's own --skill flag.

    Pi only loads a --skill file that carries Agent Skills frontmatter (a
    "name" and "description"); skills-core/<role>.md carries neither, so a
    scratch copy adds the minimal frontmatter pi requires without touching
    the asset, and the message invokes it by name via pi's own /skill:<name>
    command so pi loads the skill's content deterministically rather than
    leaving that to the model's own discretion.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks('the dispatched subprocess command includes "--model" followed by "{model}"')
    @planks('the dispatched subprocess command does not include "--model"')
    """
    scratch = Path(tempfile.mkdtemp(prefix="pce-pi-skill-"))
    try:
        wrapped = scratch / f"{role}.md"
        wrapped.write_text(
            f"---\nname: {role}\ndescription: PCE {role} role skill and task contract.\n---\n\n"
            + skill_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        cmd = [
            "pi", "-p", f"/skill:{role} {message}",
            "--skill", str(wrapped),
            "--tools", "read,bash,edit,write",
            "--no-session",
        ]
        if model is not None:
            cmd.extend(["--model", model])
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(f"pi exited {result.returncode}: {result.stderr[-2000:]}")
        return result.stdout
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def dispatch(runtime: str, role: str, task: str, cwd: Path, model: str | None = None) -> str:
    """Load a role's skill contract and run it as one turn of the chosen runtime.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    """
    skill_path = SKILLS_CORE / f"{role}.md"
    print(f"    -> dispatching {role} ({runtime}) in {cwd}", file=sys.stderr)
    if runtime == "claude":
        return run_claude(skill_path.read_text(encoding="utf-8"), task, cwd, model)
    if runtime == "pi":
        return run_pi(role, skill_path, task, cwd, model)
    return run_opencode(skill_path.read_text(encoding="utf-8"), task, cwd, model)


def resolve_model(workflow_dir: Path, role: str, runtime: str, profile_id: str | None = None) -> str | None:
    """Resolve the model pinned for a role and runtime, a critic profile's own pin taking precedence.

    @planks('the dispatched subprocess command includes "--model" followed by "{model}"')
    @planks('the dispatched subprocess command does not include "--model"')
    """
    state_path = workflow_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    model = state.get("models", {}).get(role, {}).get(runtime)
    if profile_id is not None:
        profile_model = state.get("critic_profiles", {}).get(profile_id, {}).get("model", {}).get(runtime)
        if profile_model is not None:
            model = profile_model
    return model


def schema_text(name: str) -> str:
    """Read a named JSON Schema from the shared schemas/ directory.

    @planks('it prints the fact-checker verdict and the critic verdict in its summary')
    """
    return (ROOT / "schemas" / name).read_text(encoding="utf-8")


def write_accounting_record(workflow_dir: Path, pass_id: str, role: str, runtime: str, response_text: str) -> Path:
    """Normalize a runtime's raw response and write one accounting record under accounting/history/.

    @planks('the workflow directory contains an accounting record under "accounting/history/" naming pass "{pass_id}", role "{role}", and runtime "{runtime}"')
    @planks('the response conforms to the "Accounting Record" schema in "schemas/accounting.schema.json"')
    """
    response = json.loads(response_text)
    if runtime == "claude":
        model = next(iter(response["modelUsage"]))
        input_tokens = response["usage"]["input_tokens"]
        output_tokens = response["usage"]["output_tokens"]
        cost_usd = response["total_cost_usd"]
    elif runtime == "opencode":
        model = response["info"]["model"]["id"]
        input_tokens = response["info"]["tokens"]["input"]
        output_tokens = response["info"]["tokens"]["output"]
        cost_usd = response["info"]["cost"]
    elif runtime == "pi":
        model = response["model"]
        input_tokens = response["usage"]["input"]
        output_tokens = response["usage"]["output"]
        cost_usd = response["usage"]["cost"]["total"]
    else:
        raise ValueError(f"unknown runtime {runtime!r}")

    record = {
        "pass_id": pass_id,
        "role": role,
        "profile_id": None,
        "runtime": runtime,
        "provider": None,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "total_tokens": None,
        "cost_usd": cost_usd,
        "duration_ms": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    history_dir = workflow_dir / "accounting" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    record_path = history_dir / f"{pass_id}-{role}-{runtime}-{uuid.uuid4().hex}.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return record_path


def build_dispatch_task(role: str) -> str:
    """Load a role's task-prompt text from its template file, not a hardcoded string.

    @planks("the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md")
    """
    return (ROOT / "templates" / "prompts" / f"{role}-task.md").read_text(encoding="utf-8")


def run_author(runtime: str, workflow_dir: Path) -> None:
    """Dispatch the author role and require its draft and claims outputs.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks("the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md")
    @planks("run_loop.py contains no hardcoded English sentence as that role's task text")
    """
    task = build_dispatch_task("author") + schema_text("claims.schema.json")
    model = resolve_model(workflow_dir, "author", runtime)
    dispatch(runtime, "author", task, workflow_dir, model)
    if not (workflow_dir / "drafts" / "current.md").is_file():
        raise RuntimeError("author did not write drafts/current.md")
    if not (workflow_dir / "claims" / "current.json").is_file():
        raise RuntimeError("author did not write claims/current.json")


def run_archivist(runtime: str, workflow_dir: Path) -> None:
    """Dispatch the archivist role and require a preserved draft snapshot.

    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks("the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md")
    @planks("run_loop.py contains no hardcoded English sentence as that role's task text")
    """
    task = build_dispatch_task("archivist") + PASS_ID
    model = resolve_model(workflow_dir, "archivist", runtime)
    dispatch(runtime, "archivist", task, workflow_dir, model)
    draft_glob = to_glob(parse_scope("archivist", "## Write Scope")[0], **{"pass-id": PASS_ID})
    if not globmod.glob(draft_glob, root_dir=workflow_dir):
        raise RuntimeError(f"archivist did not write a draft snapshot matching {draft_glob}")


def run_fact_checker(runtime: str, workflow_dir: Path) -> dict:
    """Dispatch the fact-checker role in an isolated staged workspace and collect its verdict.

    @planks('the staged workspace does not contain "{relpath}"')
    @planks('the workflow directory contains "{relpath}"')
    @planks('it prints the fact-checker verdict and the critic verdict in its summary')
    @planks("the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md")
    @planks("run_loop.py contains no hardcoded English sentence as that role's task text")
    """
    read_patterns = parse_scope("fact-checker", "## Read Scope")
    write_patterns = [
        substitute(p, **{"pass-id": PASS_ID}) for p in parse_scope("fact-checker", "## Write Scope")
    ]
    model = resolve_model(workflow_dir, "fact-checker", runtime)
    staged = stage_workspace(workflow_dir, read_patterns)
    try:
        task = (
            build_dispatch_task("fact-checker")
            + PASS_ID
            + schema_text("fact-check.schema.json")
        )
        dispatch(runtime, "fact-checker", task, staged, model)
        current = staged / "reviews" / "current" / "fact-check.json"
        if not current.is_file():
            raise RuntimeError("fact-checker did not write reviews/current/fact-check.json")
        verdict = json.loads(current.read_text(encoding="utf-8"))
        collect_back(staged, workflow_dir, write_patterns)
        return verdict
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def run_critic(runtime: str, workflow_dir: Path, profile_id: str, remit: str) -> dict:
    """Dispatch a critic profile in an isolated staged workspace and collect its verdict.

    @planks('the staged workspace does not contain "{relpath}"')
    @planks('the workflow directory contains "{relpath}"')
    @planks('it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order')
    @planks("the task argument that call passes to dispatch() starts with the content of templates/prompts/{role}-task.md")
    @planks("run_loop.py contains no hardcoded English sentence as that role's task text")
    """
    read_patterns = parse_scope("critic", "## Read Scope")
    write_patterns = [
        substitute(p, **{"pass-id": PASS_ID, "profile-id": profile_id})
        for p in parse_scope("critic", "## Write Scope")
    ]
    model = resolve_model(workflow_dir, "critic", runtime, profile_id)
    staged = stage_workspace(workflow_dir, read_patterns)
    try:
        task = (
            build_dispatch_task("critic")
            + f"{PASS_ID}\n{profile_id}\n{remit}\n\n"
            + (ROOT / "templates" / "reviews" / "critic.md").read_text(encoding="utf-8")
        )
        dispatch(runtime, "critic", task, staged, model)
        current = staged / "reviews" / "current" / f"critic-{profile_id}.md"
        if not current.is_file():
            raise RuntimeError(f"critic({profile_id}) did not write its current review")
        text = current.read_text(encoding="utf-8")
        match = re.search(r"Verdict:\s*(\S+)", text)
        collect_back(staged, workflow_dir, write_patterns)
        return {"profile": profile_id, "verdict": match.group(1) if match else "unknown", "raw": text}
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def main() -> int:
    """Run one bounded pass: author, archivist, then each configured gate in state.json.

    @planks('it reports that "{filename}" was not found')
    @planks('it exits with status {code:d}')
    @planks('it exits 0 only when every verdict is "pass" or "approve"')
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_dir", type=Path, help="Project workspace holding brief.md, sources/, etc.")
    parser.add_argument("--runtime", choices=["claude", "opencode", "pi"], required=True)
    args = parser.parse_args()

    workflow_dir = args.workflow_dir.resolve()
    if not (workflow_dir / "brief.md").is_file():
        print(f"error: {workflow_dir}/brief.md not found", file=sys.stderr)
        return 2

    for sub in ("drafts", "claims", "reviews/history", "reviews/current", "revisions/history"):
        (workflow_dir / sub).mkdir(parents=True, exist_ok=True)

    state = json.loads((workflow_dir / "state.json").read_text(encoding="utf-8"))

    print("== author ==")
    run_author(args.runtime, workflow_dir)
    print("== archivist ==")
    run_archivist(args.runtime, workflow_dir)

    verdicts = []
    for gate in state["required_gates"]:
        print(f"== gate: {gate} ==")
        if gate == "fact-checker":
            verdicts.append(("fact-checker", run_fact_checker(args.runtime, workflow_dir)["verdict"]))
        elif gate == "critic":
            for profile_id, cfg in state.get("critic_profiles", {}).items():
                result = run_critic(args.runtime, workflow_dir, profile_id, cfg["remit"])
                verdicts.append((f"critic:{profile_id}", result["verdict"]))
        elif gate == "specialist":
            print("specialist gate not yet wired into this tiny runner", file=sys.stderr)
        else:
            raise RuntimeError(f"unknown gate {gate!r}")

    print("\n== summary ==")
    ok = True
    for name, verdict in verdicts:
        print(f"{name}: {verdict}")
        if verdict not in ("pass", "approve"):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
