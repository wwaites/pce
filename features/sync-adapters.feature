Feature: Runtime skill adapter generation

  Rule: Adapters under adapters/opencode/skills and adapters/claude/skills,
  and the plugin-root skills/ directory that Claude Code's plugin loader
  auto-discovers, are generated from the canonical role contracts under
  skills-core. Nobody hand-edits a generated adapter file.

  Scenario: Sync writes a missing adapter file from its canonical source
    Given adapters/claude/skills/archivist/SKILL.md does not exist
    When sync-adapters.py runs without "--check"
    Then adapters/claude/skills/archivist/SKILL.md is written
    And its frontmatter carries "name: archivist" and the archivist description
    And its body is the current text of skills-core/archivist.md

  @contract
  Scenario: Check fails when a canonical source is missing required policy text
    Given skills-core/author.md no longer contains "Author hands off to `archivist`."
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it names the missing policy phrase for "skills-core/author.md"

  @contract
  Scenario: Check fails when a canonical source carries a forbidden pattern
    Given skills-core/critic.md contains the word "Pilot"
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it names the forbidden pattern found in "skills-core/critic.md"

  @contract
  Scenario: Check fails when a generated adapter has drifted from its source
    Given adapters/opencode/skills/editor/SKILL.md differs from the text sync-adapters.py would generate
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it reports "generated adapter drift" for "opencode/editor"
    And it prints a unified diff between the existing file and the expected text

  @contract
  Scenario: Check fails when an adapter skill directory carries an unexpected file
    Given adapters/claude/skills/fact-checker/ contains an extra file "notes.txt"
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it names "notes.txt" as an unexpected file under "claude/fact-checker"

  Scenario: Sync writes the plugin-root skill copy identical to the Claude adapter
    Given the plugin-root copy of skills/archivist/SKILL.md does not exist
    When sync-adapters.py runs without "--check"
    Then skills/archivist/SKILL.md is written
    And its body is the current text of skills-core/archivist.md

  @contract
  Scenario: Check fails when the plugin-root skill copy has drifted from the Claude adapter
    Given the plugin-root copy of skills/editor/SKILL.md differs from the text sync-adapters.py would generate
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it reports "generated adapter drift" for "skills/editor"

  @contract
  Scenario: Check fails when the plugin-root skills directory does not exist at all
    Given the plugin-root skills directory does not exist
    When sync-adapters.py runs with "--check"
    Then the check exits non-zero
    And it names "skills" as missing
