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
