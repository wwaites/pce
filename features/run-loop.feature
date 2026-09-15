Feature: Bounded review-pass runner

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

  Rule: Every role dispatch also writes one accounting record, since the
  chosen runtime already reports its own token counts and cost in the same
  response run_loop.py currently discards after pulling out the role's
  output file. Only the dispatcher ever sees a runtime's raw response, so
  writing the record can never be a dispatched role's own duty; run_loop.py
  writes it. A field the chosen runtime does not report in a given response
  is recorded as null, never estimated. The "opencode" runtime's streamed
  run events carry token and cost figures but not the model name, so its
  dispatch also calls "opencode export <sessionID>" after the run completes
  to recover the model from the exported session record.

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
      | archivist    | opencode | info.model.id   | Qwen/Qwen3.5-397B-A17B-FP8 | info.tokens.input   | 8945  | info.tokens.output   | 39     | info.cost         | 0      |
      | fact-checker | pi       | model           | Qwen/Qwen3.5-397B-A17B-FP8 | usage.input          | 1094  | usage.output         | 46     | usage.cost.total  | 0      |
      | critic       | claude   | modelUsage key  | claude-sonnet-5            | usage.input_tokens  | 2     | usage.output_tokens  | 4      | total_cost_usd    | 0.0388 |

  @contract
  Scenario: An accounting record conforms to its schema
    Given an accounting record written for a role dispatch
    When the record is checked against the "Accounting Record" schema
    Then the response conforms to the "Accounting Record" schema in "schemas/accounting.schema.json"

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
