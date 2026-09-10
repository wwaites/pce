# Artificial Organisation

This pack reimplements the useful core of William Waites's `Artificial Organisations` pattern in a lightweight form.

## Goal

Make the overall workflow reliable through role structure, review boundaries, durable handoffs, and fresh review passes.

## Role Family

- `editor`: human-facing remit and acceptance decisions
- `author`: source-grounded drafting
- `fact-checker`: adversarial fact checking against approved external sources
- `critic`: blind quality review without access to internal notes
- `specialist`: optional subject-matter review for bounded specialist questions
- `archivist`: append-only custody for full draft snapshots and provenance records

In runtime adapters, `editor` is the human-facing entry skill. An overview skill may also exist for pack discovery.

## Entry Points

- `editor`: direct human-facing workflow control
- `artificial-org`: overview and role routing

## Artifacts

- `brief.md`
- `sources/internal/`
- `sources/external/`
- `drafts/current.md`
- `claims/current.json`
- `reviews/current/fact-check.json`
- `reviews/current/critic-<profile-id>.md`
- `reviews/current/specialist-<question-id>.md`
- `reviews/editor-feedback.md`
- `reviews/history/`
- `revisions/history/`
- `state.json`

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
parallel as one pass. Critic scores are advisory only; acceptance is an editor
judgement from concrete findings. For mixed-reviewer venues, define diverse
critic profiles instead of relying on one generic critic.

## Routing

Editor is the sole workflow dispatcher. Author hands every substantive draft to
Archivist before review. Archivist returns the preserved draft to Editor. Each
reviewer returns its verdict to Editor, which routes the next configured gate,
requests revision, or accepts the result.

One configured gate may have several independent instances. A `critic` gate runs
every configured critic profile. A `specialist` gate runs every named specialist
question. `state.json` keys each profile and question by the stable id used in its
output filename. Each instance writes its own output, and Editor waits for all
instances in that gate before routing onward.

`state.json` records the ordered `required_gates`. Risk supplies a default when
Editor creates the state file; it is not a second routing authority:

- low risk: no review gate by default
- medium risk: `fact-checker`
- high risk: `fact-checker`, then `critic`
- specialist review: add `specialist` only with one or more named questions that can change acceptance

Archivist custody applies at every risk level and is not an optional review gate.

## Context Hygiene

1. Cross-role handoff happens through durable files, not hidden chat state.
2. `sources/internal/**` never crosses into a review gate. `sources/external/**` is in scope wherever a role's contract lists it: a reviewer is blind to the workflow's internal process, not to what an informed reader could find on their own.
3. Reviewers do not read previous reviews or editor-only notes; each review is fresh.
4. `specialist` sees only the minimum subset needed for the specialist question.
5. Accepted factual claims must carry evidence.
6. Reviews, fact checks, specialist opinions, revision notes, and full draft snapshots are append-only records.
7. Author may read prior reviews and fact checks when revising.
8. Roles are added only when their error reduction beats their coordination cost.

## Runtime Principle

The workflow is runtime-neutral.

- Skills may be installed anywhere.
- Work always happens against the current project workspace.
- Runtime adapters only translate the same role contracts into loader-specific `SKILL.md` files.
