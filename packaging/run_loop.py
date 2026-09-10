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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_CORE = ROOT / "skills-core"
PASS_ID = "pass1"
TIMEOUT_SECONDS = 600


def parse_scope(role: str, heading: str) -> list[str]:
    """Extract backtick-quoted path patterns from a role's Read Scope or Write Scope section."""
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
    for key, value in placeholders.items():
        pattern = pattern.replace(f"<{key}>", value)
    return pattern


def to_glob(pattern: str, **placeholders: str) -> str:
    """Substitute known placeholders, then turn any remaining <...> token into a glob wildcard."""
    return re.sub(r"<[^>]+>", "*", substitute(pattern, **placeholders))


def stage_workspace(workflow_dir: Path, patterns: list[str]) -> Path:
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


def run_claude(system_prompt: str, message: str, cwd: Path) -> str:
    cmd = [
        "claude", "-p", message,
        "--append-system-prompt", system_prompt,
        "--tools", "Read,Write,Edit,Glob",
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--output-format", "json",
    ]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def run_opencode(system_prompt: str, message: str, cwd: Path) -> str:
    combined = f"{system_prompt}\n\n---\n\nTask:\n\n{message}"
    cmd = ["opencode", "run", combined, "--dir", str(cwd), "--format", "json"]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(f"opencode exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def dispatch(runtime: str, role: str, task: str, cwd: Path) -> str:
    skill = (SKILLS_CORE / f"{role}.md").read_text(encoding="utf-8")
    print(f"    -> dispatching {role} ({runtime}) in {cwd}", file=sys.stderr)
    if runtime == "claude":
        return run_claude(skill, task, cwd)
    return run_opencode(skill, task, cwd)


def schema_text(name: str) -> str:
    return (ROOT / "schemas" / name).read_text(encoding="utf-8")


def run_author(runtime: str, workflow_dir: Path) -> None:
    task = (
        "Read brief.md and the approved source pack in this directory, per your Read Scope. "
        "Write your draft to drafts/current.md. Extract material factual claims into "
        "claims/current.json using exactly this JSON Schema shape, an array of claim objects, "
        f"claim ids c1, c2, ...:\n\n{schema_text('claims.schema.json')}"
    )
    dispatch(runtime, "author", task, workflow_dir)
    if not (workflow_dir / "drafts" / "current.md").is_file():
        raise RuntimeError("author did not write drafts/current.md")
    if not (workflow_dir / "claims" / "current.json").is_file():
        raise RuntimeError("author did not write claims/current.json")


def run_archivist(runtime: str, workflow_dir: Path) -> None:
    task = (
        f"Pass id \"{PASS_ID}\". Preserve the full text of drafts/current.md and a revision note "
        "under revisions/history/, per your Write Scope and Rule 3 above (unique, sortable "
        "filenames that include the date and pass id)."
    )
    dispatch(runtime, "archivist", task, workflow_dir)
    draft_glob = to_glob(parse_scope("archivist", "## Write Scope")[0], **{"pass-id": PASS_ID})
    if not globmod.glob(draft_glob, root_dir=workflow_dir):
        raise RuntimeError(f"archivist did not write a draft snapshot matching {draft_glob}")


def run_fact_checker(runtime: str, workflow_dir: Path) -> dict:
    read_patterns = parse_scope("fact-checker", "## Read Scope")
    write_patterns = [
        substitute(p, **{"pass-id": PASS_ID}) for p in parse_scope("fact-checker", "## Write Scope")
    ]
    staged = stage_workspace(workflow_dir, read_patterns)
    try:
        task = (
            f"Pass id \"{PASS_ID}\". This workspace contains only your Read Scope; "
            "sources/internal/** is intentionally absent. Check every claim in "
            "claims/current.json against sources/external/**. Write your verdict to "
            f"reviews/history/{PASS_ID}-fact-check.json and reviews/current/fact-check.json "
            f"using exactly this JSON Schema shape:\n\n{schema_text('fact-check.schema.json')}"
        )
        dispatch(runtime, "fact-checker", task, staged)
        current = staged / "reviews" / "current" / "fact-check.json"
        if not current.is_file():
            raise RuntimeError("fact-checker did not write reviews/current/fact-check.json")
        verdict = json.loads(current.read_text(encoding="utf-8"))
        collect_back(staged, workflow_dir, write_patterns)
        return verdict
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def run_critic(runtime: str, workflow_dir: Path, profile_id: str, remit: str) -> dict:
    read_patterns = parse_scope("critic", "## Read Scope")
    write_patterns = [
        substitute(p, **{"pass-id": PASS_ID, "profile-id": profile_id})
        for p in parse_scope("critic", "## Write Scope")
    ]
    staged = stage_workspace(workflow_dir, read_patterns)
    try:
        task = (
            f"Pass id \"{PASS_ID}\", profile id \"{profile_id}\". Profile remit: {remit}. "
            "This workspace contains only your Read Scope; sources/**, prior reviews, and "
            "editor-only notes are intentionally absent. Review drafts/current.md fresh. "
            f"Write your review to reviews/history/{PASS_ID}-{profile_id}-critic.md and "
            f"reviews/current/critic-{profile_id}.md using exactly this shape:\n\n"
            + (ROOT / "templates" / "reviews" / "critic.md").read_text(encoding="utf-8")
        )
        dispatch(runtime, "critic", task, staged)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_dir", type=Path, help="Project workspace holding brief.md, sources/, etc.")
    parser.add_argument("--runtime", choices=["claude", "opencode"], required=True)
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
