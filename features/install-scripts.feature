Feature: Local install scripts

  Rule: Each install script copies the shipped skill-pack content into the
  user's data directory and the target runtime's skill directory, replacing
  any prior install of the same skills.

  Scenario: Installing for Claude places support files and skill adapters
    Given XDG_DATA_HOME and HOME point at empty temporary directories
    When packaging/install-claude.sh runs
    Then "$XDG_DATA_HOME/artificial-org" contains skills-core, schemas, templates, and adapters
    And "$HOME/.claude/skills" contains one directory per skill under adapters/claude/skills

  Scenario: Installing for opencode places support files and skill adapters
    Given XDG_DATA_HOME, XDG_CONFIG_HOME, and HOME point at empty temporary directories
    When packaging/install-opencode.sh runs
    Then "$XDG_DATA_HOME/artificial-org" contains skills-core, schemas, templates, and adapters
    And "$XDG_CONFIG_HOME/opencode/skills" contains one directory per skill under adapters/opencode/skills

  Scenario: Reinstalling for Claude replaces a stale prior install
    Given "$HOME/.claude/skills/critic" already exists with a stale file "old.md"
    When packaging/install-claude.sh runs
    Then "$HOME/.claude/skills/critic" no longer contains "old.md"
    And "$HOME/.claude/skills/critic/SKILL.md" matches adapters/claude/skills/critic/SKILL.md
