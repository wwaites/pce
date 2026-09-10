# Artifacts

The workflow depends on project artifacts, not on the skill installation path.

## Required Files

- `brief.md`: task remit, audience, scope, acceptance bar, and any named specialist questions
- `sources/internal/`: author and editor working material such as notes, rationale, and framing. No real external reviewer has access to this; it never crosses into a review gate.
- `sources/external/`: approved public, citable reference material. An informed reader could find this independently; it is in scope for any role whose contract lists it.
- `drafts/current.md`: current draft under review
- `claims/current.json`: extracted factual claims from the draft
- `reviews/current/fact-check.json`: latest fact-checker verdicts with evidence
- `reviews/current/critic-<profile-id>.md`: latest blind review for one configured critic profile
- `reviews/current/specialist-<question-id>.md`: latest specialist review for one named question
- `reviews/editor-feedback.md`: optional editor-curated revision instructions for the author
- `reviews/history/`: append-only fact-check, critic, and specialist records
- `revisions/history/`: append-only revision notes and full draft snapshots
- `state.json`: risk level, ordered required gates, loop limits, and advisory score policy

## Schemas

- `schemas/claims.schema.json`
- `schemas/fact-check.schema.json`
- `schemas/state.schema.json`

## Templates

- `templates/brief.md`
- `templates/state.json`
- `templates/reviews/editor-feedback.md`
- `templates/reviews/critic.md`
- `templates/reviews/specialist.md`

## Read Scope Principle

A role's Read Scope is bounded by what a real party filling that role could plausibly access on their own. `sources/internal/**` and other reviewers' verdicts have no real-world counterpart for a fresh reviewer and never cross into a review gate. `sources/external/**` does have a real-world counterpart, since an informed reader can find it independently, and is in scope wherever a role's contract lists it.

## Handoff Rule

If one role wants another role to know something important, it must write it into one of these artifacts.

## Snapshot Rule

Every substantive draft pass must pass through Archivist, which preserves the
full draft text in `revisions/history/` before Editor dispatches a review gate or
considers acceptance. A revision note is not enough. If `drafts/current.md` is
only a pointer to a live source elsewhere, snapshot the live source text, not
the pointer.

Reviewers must not read `sources/internal/**`, `reviews/history/`, `reviews/current/`, or editor-only notes unless their role contract explicitly permits that exact file. The author may read prior reviews and fact checks when revising. The fresh-context rule protects reviewers, not the author.
