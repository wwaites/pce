#!/usr/bin/env python3
"""Generate runtime skill adapters from the canonical role contracts."""
from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = ("opencode", "claude")
SKILLS = {
    "artificial-org": (
        "overview.md",
        "Lightweight artificial-organisation workflow, editorial role routing, or Editor Author Archivist Fact-Checker Critic Specialist usage. Use when a task needs packaged drafting, draft snapshots, fact checking, blind review, and optional subject-matter escalation.",
    ),
    "archivist": (
        "archivist.md",
        "Draft snapshot custody, provenance records, and append-only revision history in the artificial-organisation workflow. Use when a draft must be preserved before fact-check, critic review, or acceptance.",
    ),
    "author": (
        "author.md",
        "Drafting, outline, first pass, rewrite, or synthesis from brief.md and sources/. Use when a task needs a source-grounded draft in the artificial-organisation workflow.",
    ),
    "critic": (
        "critic.md",
        "Blind review, fresh eyes, clarity review, argument quality, completeness, or reader-risk review over drafts/current.md. Use when a draft needs quality review without access to the author's internal notes.",
    ),
    "editor": (
        "editor.md",
        "Briefing, remit, acceptance, source-pack setup, draft-snapshot enforcement, workflow routing, or final approval in the artificial-organisation workflow. Use when the human-facing role must define the task or decide whether the draft is ready.",
    ),
    "fact-checker": (
        "fact-checker.md",
        "Fact checking, citations, evidence review, unsupported claims, or adversarial verification over drafts/current.md and sources/external/. Use when factual claims must be checked against approved external sources.",
    ),
    "specialist": (
        "specialist.md",
        "Subject-matter expert review, domain terminology, specialist judgment, or risky local knowledge. Use ONLY when a named specialist question changes acceptance of the draft.",
    ),
}

FORBIDDEN_PATTERNS = (
    re.compile(r"\bPilot\b", re.IGNORECASE),
    re.compile(r"score.{0,40}(?:below|above).{0,20}threshold", re.IGNORECASE),
)
REQUIRED_POLICY = {
    "overview.md": ("Archivist custody applies at every risk level",),
    "author.md": ("Author hands off to `archivist`.",),
    "archivist.md": ("return control to `editor`",),
    "critic.md": (
        "Treat the score as advisory.",
        "A numeric score alone never determines acceptance or revision.",
    ),
}


def render(name: str, source_name: str, description: str) -> str:
    """Render a runtime skill adapter's frontmatter and body from its canonical source.

    @planks("adapters/{runtime}/skills/{name}/SKILL.md is written")
    """
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError(f"invalid skill name: {name!r}")
    if not description.strip() or "\n" in description:
        raise ValueError(f"invalid skill description for {name}")
    body = (ROOT / "skills-core" / source_name).read_text(encoding="utf-8")
    rendered = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}"
    validate_frontmatter(rendered, name)
    return rendered


def validate_frontmatter(text: str, expected_name: str) -> None:
    """Check a rendered adapter's frontmatter block carries exactly name and description.

    @planks("adapters/{runtime}/skills/{name}/SKILL.md is written")
    """
    opening, separator, remainder = text.partition("\n---\n")
    if not separator or not opening.startswith("---\n") or not remainder.strip():
        raise ValueError(f"invalid frontmatter block for {expected_name}")
    fields = {}
    for line in opening[4:].splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise ValueError(f"invalid frontmatter line for {expected_name}: {line!r}")
        fields[key.strip()] = value.strip()
    if set(fields) != {"name", "description"}:
        raise ValueError(f"invalid frontmatter fields for {expected_name}: {sorted(fields)}")
    if fields["name"] != expected_name:
        raise ValueError(f"frontmatter name mismatch for {expected_name}")


def check_policy() -> list[str]:
    """Check every canonical source carries its required policy phrases and no forbidden pattern.

    @planks('it names the missing policy phrase for "{source_path}"')
    @planks('it names the forbidden pattern found in "{source_path}"')
    """
    failures = []
    for source_name, required in REQUIRED_POLICY.items():
        text = (ROOT / "skills-core" / source_name).read_text(encoding="utf-8")
        for phrase in required:
            if phrase not in text:
                failures.append(f"skills-core/{source_name}: missing policy {phrase!r}")
    for source_name, _description in SKILLS.values():
        text = (ROOT / "skills-core" / source_name).read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                failures.append(
                    f"skills-core/{source_name}: forbidden policy pattern {pattern.pattern!r}"
                )
    return failures


def main() -> int:
    """Generate or check every runtime skill adapter against its canonical source.

    @planks("adapters/{runtime}/skills/{name}/SKILL.md is written")
    @planks('it reports "{message}" for "{location}"')
    @planks('it names "{filename}" as an unexpected file under "{location}"')
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    failures = check_policy()
    for runtime in RUNTIMES:
        skill_root = ROOT / "adapters" / runtime / "skills"
        if not skill_root.exists():
            if args.check:
                failures.append(f"{runtime}: missing adapter root {skill_root}")
                continue
            skill_root.mkdir(parents=True)
        expected_names = set(SKILLS)
        actual_names = {path.name for path in skill_root.iterdir()}
        unexpected_names = actual_names - expected_names
        missing_names = expected_names - actual_names
        if unexpected_names:
            failures.append(f"{runtime}: unexpected adapter directories {sorted(unexpected_names)}")
        if args.check and missing_names:
            failures.append(f"{runtime}: missing adapter directories {sorted(missing_names)}")
        for name, (source_name, description) in SKILLS.items():
            destination = ROOT / "adapters" / runtime / "skills" / name / "SKILL.md"
            if not destination.parent.exists():
                if args.check:
                    continue
                destination.parent.mkdir(parents=True)
            extras = set(destination.parent.iterdir()) - {destination}
            if extras:
                failures.append(
                    f"{runtime}/{name}: unexpected files "
                    + ", ".join(sorted(str(path) for path in extras))
                )
            expected = render(name, source_name, description)
            actual = destination.read_text(encoding="utf-8") if destination.exists() else ""
            if actual == expected:
                continue
            if args.check:
                failures.append(f"{runtime}/{name}: generated adapter drift")
                print(
                    "".join(
                        difflib.unified_diff(
                            actual.splitlines(keepends=True),
                            expected.splitlines(keepends=True),
                            fromfile=str(destination),
                            tofile=f"generated from skills-core/{source_name}",
                        )
                    ),
                    end="",
                )
            else:
                destination.write_text(expected, encoding="utf-8")

    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
