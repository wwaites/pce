Feature: Bounded review-pass runner

  Rule: The Nix package installs a stable "pce" executable so downstream
  projects can run a bounded pass without importing PCE source paths. The
  command accepts the same workflow directory and "--runtime" argument as
  run_loop.py.

  Scenario: The packaged pce command runs the bounded-pass runner
    Given the PCE Nix package is installed
    And a workflow directory with no "brief.md" file
    When the "pce" command runs against that directory with "--runtime claude"
    Then it exits with status 2
    And it reports that "brief.md" was not found

  Scenario: Source and packaged runners resolve the same bounded-pass resources
    Given packaging/run_loop.py in the source tree
    And run_loop.py installed under the PCE Nix package libexec directory
    When each bounded-pass runner resolves its runtime resources
    Then each runner finds the "author", "archivist", "fact-checker", and "critic" role skills
    And each runner finds the "author", "archivist", "fact-checker", and "critic" task prompts
    And each runner finds the "claims.schema.json", "fact-check.schema.json", and "accounting.schema.json" schemas
    And each runner finds the critic review instructions

  Scenario: The default flake app runs the packaged pce command
    When the default flake app runs with "--help"
    Then it exits with status 0
    And it reports the bounded review-pass runner help

  Rule: run_loop.py dispatches each artificial-organisation role as a real
  subprocess of the chosen agent runtime, staging a scratch workspace for
  reviewer roles so a reviewer's file tools cannot reach material outside
  its Read Scope, per skills-core/<role>.md.

  Scenario: Runner refuses a workflow directory with no brief
    Given a workflow directory with no "brief.md" file
    When run_loop.py runs against that directory with "--runtime claude"
    Then it exits with status 2
    And it reports that "brief.md" was not found

  Scenario: Runner reads a role's read-scope patterns from its skill file
    Given skills-core/fact-checker.md has a "## Read Scope" section listing "brief.md" and "sources/external/**"
    When run_loop.py parses the fact-checker read scope
    Then it returns exactly the patterns "brief.md" and "sources/external/**"

  Scenario: Staged reviewer workspace excludes internal sources
    Given a workflow directory containing "sources/internal/notes.md" and "sources/external/spec.md"
    And the fact-checker read scope names only "sources/external/**"
    When run_loop.py stages a workspace for the fact-checker
    Then the staged workspace contains "sources/external/spec.md"
    And the staged workspace does not contain "sources/internal/notes.md"

  Scenario: Collected write-scope files land back in the workflow directory
    Given a staged workspace containing "reviews/current/fact-check.json"
    And the fact-checker write scope names "reviews/current/**"
    When run_loop.py collects the write scope back from the staged workspace
    Then the workflow directory contains "reviews/current/fact-check.json"

  Scenario: A scope pattern with a placeholder resolves to a glob
    Given the write-scope pattern "revisions/history/<pass-id>-*.md"
    When run_loop.py resolves it for pass id "pass1"
    Then the resulting glob is "revisions/history/pass1-*.md"

  Rule: The remaining role dispatches invoke a real "claude", "opencode", or
  "pi" CLI subprocess and need a @sandbox tier with real runtime credentials.
  The "pi" runtime loads a role's skill file directly with pi's own
  "--skill" flag rather than folding it into a system-prompt string.

  @sandbox
  Scenario Outline: Runner completes a bounded pass on each supported runtime and reports each gate's verdict
    Given a workflow directory with "brief.md", "state.json" naming the "fact-checker" and "critic" gates, and an approved source pack
    When run_loop.py runs against that directory with "--runtime <runtime>"
    Then it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order
    And it prints the fact-checker verdict and the critic verdict in its summary
    And it exits 0 only when every verdict is "pass" or "approve"

    Examples:
      | runtime  |
      | claude   |
      | opencode |
      | pi       |

  @sandbox
  Scenario Outline: Packaged pce preserves bounded-pass artifacts on selectable runtimes
    Given the PCE Nix package is installed
    And a workflow directory with "brief.md", "state.json" naming the "fact-checker" and "critic" gates, and an approved source pack
    When the "pce" command runs against that directory with "--runtime <runtime>"
    Then the packaged pass dispatches "author", "archivist", "fact-checker", and "critic" through the selected runtime in order
    And the workflow directory contains one normalized accounting record for each successful role dispatch in that order
    And the critic accounting record names profile "reviewer"
    And the packaged pass reports the fact-checker and critic verdicts
    And the packaged pass exits 0 only when every verdict is "pass" or "approve"

    Examples:
      | runtime  |
      | opencode |
      | pi       |

  Scenario: A failed runtime dispatch reports its captured evidence
    Given a role dispatch whose runtime exits non-zero with empty stderr
    And the runtime writes output and structured events to stdout
    When run_loop.py reports the dispatch failure
    Then the failure names the role, runtime, and exit status
    And the failure includes the captured stdout and structured events

  Rule: OpenCode accounting is derived from the complete NDJSON event stream
  emitted by "opencode run --format json". Each dispatch preserves that raw
  event stream as audit evidence. Accounting does not depend on a monolithic
  session export.

  Scenario: OpenCode accounting is normalized from complete run events
    Given a successful OpenCode role dispatch whose NDJSON run events report token usage and cost across multiple events
    When run_loop.py records accounting for that dispatch
    Then it derives the normalized token counts and cost from all reported run events
    And it preserves the complete NDJSON run events as raw evidence
    And it does not call "opencode export"

  Scenario: OpenCode fields absent from run events remain unknown
    Given a successful OpenCode role dispatch whose NDJSON run events report no provider, model, or duration
    When run_loop.py records accounting for that dispatch
    Then the accounting record's provider is null
    And the accounting record's model is null
    And the accounting record's duration_ms is null
    And it preserves the complete NDJSON run events as raw evidence

  Rule: Every role dispatch also writes one accounting record, since the
  chosen runtime already reports its own token counts and cost in the same
  response run_loop.py currently discards after pulling out the role's
  output file. Only the dispatcher ever sees a runtime's raw response, so
  writing the record can never be a dispatched role's own duty; run_loop.py
  writes it. A field the chosen runtime does not report in a given response
  is recorded as null, never estimated.

  Scenario Outline: A role dispatch writes an accounting record normalized from the runtime's own response
    Given run_loop.py dispatches the "<role>" role in pass "pass1" through the "<runtime>" runtime
    And that runtime's response reports "<model_field>" "<model>", "<input_field>" <input>, "<output_field>" <output>, and "<cost_field>" <cost>
    When that dispatch completes
    Then the workflow directory contains an accounting record under "accounting/history/" naming pass "pass1", role "<role>", and runtime "<runtime>"
    And that record's model is "<model>"
    And that record's input_tokens is <input>
    And that record's output_tokens is <output>
    And that record's cost_usd is <cost>

    Examples:
      | role         | runtime  | model_field     | model                      | input_field         | input | output_field         | output | cost_field        | cost   |
      | author       | claude   | modelUsage key  | claude-sonnet-5            | usage.input_tokens  | 2     | usage.output_tokens  | 4      | total_cost_usd    | 0.0388 |
      | fact-checker | pi       | model           | Qwen/Qwen3.5-397B-A17B-FP8 | usage.input          | 1094  | usage.output         | 46     | usage.cost.total  | 0      |
      | critic       | claude   | modelUsage key  | claude-sonnet-5            | usage.input_tokens  | 2     | usage.output_tokens  | 4      | total_cost_usd    | 0.0388 |

  @contract
  Scenario: An accounting record conforms to its schema
    Given an accounting record written for a role dispatch
    When the record is checked against the "Accounting Record" schema
    Then the response conforms to the "Accounting Record" schema in "schemas/accounting.schema.json"

  Rule: The runner exposes a stable machine interface for completed editorial
  outcomes and execution failures. Exit status 0 means approved completion,
  exit status 1 means completed revision-required, and exit status 2 means an
  execution, configuration, or runtime failure. Every completed editorial run
  emits one JSON summary with its completion state and ordered gate verdicts.

  Scenario: An all-approved editorial run exits successfully
    Given a bounded pass whose required gates return "pass" and "approve"
    When run_loop.py completes the pass
    Then it exits with status 0

  Scenario: A completed revision-required editorial run has a distinct exit status
    Given a bounded pass whose required critic gate returns "revise"
    When run_loop.py completes the pass
    Then it exits with status 1

  Scenario: An execution failure uses the execution-failure exit class
    Given a bounded pass whose required gate runtime fails
    When run_loop.py stops the pass
    Then it exits with status 2

  @contract
  Scenario: A completed editorial run emits its machine-readable outcome
    Given a bounded pass whose required gates return "pass" and "revise"
    When run_loop.py completes the pass
    Then it emits one JSON completion summary with completion_state "revision_required"
    And the summary lists the ordered gate verdicts "fact-checker: pass" and "critic: revise"

  Rule: Task-prompt text sent to each dispatched role lives under templates/,
  not as hardcoded strings in run_loop.py, so it stays reviewable and
  editable as content rather than code, per the Asset policy PCE's own
  workflow applies to its editorial roles. A role's dynamic content, such as
  a JSON Schema or a computed pass id, may still be appended after the
  template text; the template carries the English instruction.

  Scenario Outline: A role's dispatched task begins with its template, not a hardcoded instruction
    Given templates/prompts/<role>-task.md exists with that role's task instructions
    When run_<role> in run_loop.py runs a real pass and reaches its call to dispatch()
    Then the task argument that call passes to dispatch() starts with the content of templates/prompts/<role>-task.md
    And run_loop.py contains no hardcoded English sentence as that role's task text

    Examples:
      | role         |
      | author       |
      | archivist    |
      | fact-checker |
      | critic       |

  Rule: state.json MAY pin a model for a role, and independently for each
  critic profile, keyed by runtime name so the same pin survives a
  "--runtime" switch — a runtime-agnostic value could not, since "claude",
  "opencode", and "pi" each expect a different model-name format. A critic
  profile's own pin overrides that role's top-level default under "models";
  neither present leaves the dispatch on the chosen runtime's own default
  model. A pin with no entry for the active runtime is treated as absent
  for that dispatch, not an error, since a jester profile pinned only to
  "claude" should not break a pass run with "--runtime opencode" — it
  simply rides that runtime's default instead of losing the guarantee
  silently.

  Scenario Outline: A role dispatch pins its model when state.json names one for the active runtime
    Given a workflow directory with state.json's "models.<role>" naming model "<model>" for runtime "<runtime>"
    When run_loop.py dispatches the "<role>" role through the "<runtime>" runtime
    Then the dispatched subprocess command includes "--model" followed by "<model>"

    Examples:
      | role         | runtime  | model                     |
      | author       | claude   | opus                      |
      | archivist    | opencode | anthropic/claude-opus-5   |
      | fact-checker | pi       | anthropic/claude-sonnet-5 |

  Scenario: A critic profile's own model pin overrides the role-level default
    Given state.json's "models.critic" names model "sonnet" for runtime "claude"
    And critic profile "jester" names model "opus" for runtime "claude"
    When run_loop.py dispatches the "jester" critic profile through the "claude" runtime
    Then the dispatched subprocess command includes "--model" followed by "opus"

  Scenario: A model pin with no entry for the active runtime leaves that dispatch unpinned
    Given critic profile "jester" names a model only for runtime "claude"
    When run_loop.py dispatches the "jester" critic profile through the "opencode" runtime
    Then the dispatched subprocess command does not include "--model"
