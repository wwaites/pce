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

  Rule: The remaining role dispatches invoke a real "claude" or "opencode"
  CLI subprocess and need a @sandbox tier with real runtime credentials.

  @sandbox
  Scenario: Runner completes a bounded pass and reports each gate's verdict
    Given a workflow directory with "brief.md", "state.json" naming the "fact-checker" and "critic" gates, and an approved source pack
    When run_loop.py runs against that directory with a real agent runtime
    Then it dispatches "author", then "archivist", then the "fact-checker" gate, then the "critic" gate, in order
    And it prints the fact-checker verdict and the critic verdict in its summary
    And it exits 0 only when every verdict is "pass" or "approve"

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
