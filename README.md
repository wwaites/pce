# Artificial Organisation Skills

This repository packages a lightweight, runtime-neutral implementation of the useful core from William Waites's `Artificial Organisations` pattern.

Target properties:

- separation of duties
- adversarial fact checking
- blind quality review
- optional subject-matter review
- draft snapshot custody
- context hygiene through durable handoffs
- fresh review passes that do not see prior reviews
- append-only records of reviews, fact checks, revisions, and full draft snapshots

## Role Family

- `editor`: human-facing remit and acceptance decisions
- `author`: source-grounded drafting
- `fact-checker`: adversarial fact checking against approved external sources
- `critic`: blind quality review without access to internal notes
- `specialist`: optional subject-matter review for bounded specialist questions
- `archivist`: append-only custody for full draft snapshots and provenance records

`editor` is the human-facing skill. `artificial-org` remains available as a pack overview skill.

## Package Layout

```text
skills-core/              runtime-neutral role contracts and workflow docs
schemas/                  JSON schemas for shared artifacts
templates/                starter artifacts for briefs, state, and reviews
adapters/opencode/skills  opencode skill wrappers, including `editor`
adapters/claude/skills    Claude skill wrappers, including `editor`
packaging/                install scripts
flake.nix                 Nix package for reproducible installs
```

## Design Rule

The skills are packaged separately from the project they operate on.

- Skills can be installed anywhere.
- Work always happens in the current workspace.
- The workflow depends on project artifacts, not on the skill install path.
- Before creating artifacts, Editor asks which directory should hold them.
- For collaborative papers, prefer a shared repository or document store over a private notes tree.

Shared artifacts:

```text
brief.md
sources/internal/          author and editor working material, never seen by a reviewer
sources/external/          approved public, citable reference material
drafts/current.md
claims/current.json
reviews/current/fact-check.json
reviews/current/critic-<profile-id>.md
reviews/current/specialist-<question-id>.md
reviews/editor-feedback.md
reviews/history/
revisions/history/        append-only revision notes and full draft snapshots
state.json
```

## Core Loop

```text
editor writes brief + source set
author writes draft + claim list
archivist records the full draft snapshot in revisions/history/
editor dispatches each required review gate from state.json in order
each reviewer returns its verdict to editor
editor returns failed or revision-required work to author
editor accepts or requests another pass by judgement against the brief
```

Formal loops are sequential. Do not run author, fact-checker, and critic in
parallel as one pass. Parallel comments may be useful advisory notes, but they do
not replace the loop order above.

Critic scores are advisory only. Do not use a numeric threshold as the acceptance
gate. For venues with mixed programme committees, the editor should define
venue-diverse critic profiles rather than relying on one generic critic.

Editor is the sole workflow dispatcher. Every substantive pass follows
`author -> archivist -> editor` before any configured review gate. Each reviewer
returns to Editor, which dispatches the next gate, requests revision, or accepts.
The ordered `required_gates` in `state.json` are the routing authority; risk only
supplies the default gate set when Editor creates that file.

A `critic` or `specialist` gate may contain several configured instances. Each
profile or named question is keyed by a stable id, receives a fresh context, and
writes a distinct current and history record. Editor waits for every instance in
the gate before routing.

## Fresh Review Rule

Reviewers do not read previous reviews, previous fact checks, or editor notes.
The author may read the accumulated review record when revising. This avoids
reviewer convergence artefacts while preserving an audit trail and giving the
author the full correction history.

## Source Material

Source material splits into `sources/internal/` (author and editor working
material: notes, rationale, framing) and `sources/external/` (approved public,
citable reference material). A role's Read Scope is bounded by what a real
party filling that role could plausibly access on their own: no real external
reviewer ever sees `sources/internal/`, so it never crosses into a review gate,
while `sources/external/` is exactly what an informed reader could find
independently, and is in scope wherever a role's contract lists it. A reviewer
is blind to the workflow's internal process, not to the public record.

Every review, fact check, and specialist opinion must be written to a unique
file under `reviews/history/` before its `reviews/current/*` pointer is updated.
Every substantive draft must pass through Archivist, which writes its revision
note and full snapshot under `revisions/history/` before review or acceptance.

## Dispatch

Target runtimes span a wide capability range, from Claude Code and opencode,
which can spawn isolated subagents, to Pi, which has no subagent primitive at
all and can only launch a fresh process of itself through its bash tool.
`skills-core/dispatch.md` names the resulting three-rung dispatch ladder
(isolated subagent, external process spawn, same-session role assumption) and
the portable workspace-staging mechanism Editor uses to keep a reviewer's
file-read tool inside its Read Scope, since no target runtime offers a
path-scoped permission system in common. A reviewer that finds material
outside its Read Scope returns a `contaminated` verdict instead of using it;
Editor discards that review and redispatches fresh.

## Packaging Modes

### Nix

The flake installs:

- runtime-neutral docs under `share/artificial-org/`
- opencode skills under `share/opencode-skills/`
- Claude skills under `share/claude-skills/`

### Scripted install

- `bash packaging/install-opencode.sh`
- `bash packaging/install-claude.sh`

These copy the canonical pack into `~/.local/share/artificial-org` and install adapter skills into the runtime-specific global skill directories.

## Local opencode Development

`.opencode/opencode.json` points opencode at `adapters/opencode/skills` for local testing from this repo.

Runtime adapters are generated from `skills-core/`. After editing a canonical
contract, regenerate and verify both adapter sets:

```bash
python3 packaging/sync-adapters.py
python3 packaging/sync-adapters.py --check
nix flake check --no-write-lock-file
```

## Why This Shape

This copies Shipshape's strongest packaging idea:

- the skill pack is a durable installable asset
- the project workspace is separate
- runtime integration is thin
- role contracts stay portable

## Next Steps

1. Add a tiny runner that executes one bounded review loop, including workspace staging per `dispatch.md`.
2. Add a conformance check proving `critic` and `fact-checker` cannot read `sources/internal/**` when run against a staged workspace.
3. Add a conformance check proving accepted drafts do not carry unsupported claims.
4. Add Codex and Pi adapters once each runtime's skill or extension install convention is confirmed; the dispatch ladder in `dispatch.md` already covers Pi's process-spawn-only model.
