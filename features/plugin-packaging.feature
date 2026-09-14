Feature: Plugin packaging

  Rule: pce installs through the same self-hosted marketplace convention
  shipshape itself ships through: a `.claude-plugin/marketplace.json` at the
  repo root listing one plugin sourced from "./", a matching
  `.claude-plugin/plugin.json` manifest, a `.plugin/plugin.json` duplicate for
  runtimes that read the open-plugin format instead of the Claude-specific
  path, and skills auto-discovered from a root-level `skills/` directory
  (generation of that directory is covered in sync-adapters.feature).

  Scenario: The plugin identifies itself as "pce", matching the installable repository
    Given the plugin manifest at ".claude-plugin/plugin.json"
    Then it declares "name" as "pce"
    And it declares "license" as "0BSD"

  Scenario: The open-plugin manifest duplicate matches the Claude Code manifest
    Given the plugin manifest at ".claude-plugin/plugin.json"
    And the plugin manifest at ".plugin/plugin.json"
    Then the two manifests are byte-identical

  Scenario: The marketplace lists the plugin sourced from the repo root
    Given the marketplace manifest at ".claude-plugin/marketplace.json"
    Then it lists a plugin named "pce" sourced from "./"

  Scenario: The declared license has a matching LICENSE file
    Then a "LICENSE" file exists at the repo root
    And it declares the "0BSD" license

  @contract
  Scenario: The Claude Code plugin manifest conforms to its schema
    Given the plugin manifest at ".claude-plugin/plugin.json"
    Then it conforms to the "plugin" schema in "schemas/plugin.schema.json"

  @contract
  Scenario: The marketplace manifest conforms to its schema
    Given the marketplace manifest at ".claude-plugin/marketplace.json"
    Then it conforms to the "marketplace" schema in "schemas/marketplace.schema.json"
