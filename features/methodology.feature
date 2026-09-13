Feature: Shipshape methodology conformance

  Rule: These scenarios guard the project's own verification method, not
  product behaviour. They are derived by Shipwright at fitting out and
  leave with the method they guard, per the Shipshape skill's Harbour flow.

  @conformance
  Scenario: Watchbill shape conforms when absent
    Given no "watchbill.json" file exists at the project root
    When the watchbill-shape conformance check runs
    Then the check reports the deck at rest with no shape violation

  @conformance
  Scenario: Perturbation quiescence holds on a green tree
    Given every file under "packaging" carries no "PERTURBATION" token
    When the perturbation-quiescence check runs
    Then the check reports no standing perturbation

  @conformance
  Scenario: Verification-conformance rule set catches a malformed plank
    Given the rule set at "scantlings/verification-conformance.json"
    And a "@planks" token placed in a bare line comment outside any docstring
    When the conformance check runs against the "plank-form" rule
    Then the check reddens naming the malformed plank

  @conformance
  Scenario: Verification-conformance rule set catches a missing plank
    Given the rule set at "scantlings/verification-conformance.json"
    And a behaviour-bearing step-definition pattern reported by step-usage with no matching plank token in the implementation paths
    When the conformance check runs against the "plank-coverage" rule
    Then the check reddens naming the uncovered step-definition pattern

  @conformance
  Scenario: The focused command selects exactly one example of a Scenario Outline
    Given a scenario reference naming one specific example row of a Scenario Outline
    When the "focused" command from RIGGING.md runs against that reference
    Then exactly one scenario runs
    And it is the named example, not zero examples and not every example

  @conformance
  Scenario: Packaging sources discharge the configured lint checker
    Given the "lint" command from RIGGING.md
    When it runs against the current text of "packaging"
    Then it exits 0
