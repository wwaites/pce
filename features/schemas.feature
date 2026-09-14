Feature: Shared artifact schemas

  Rule: schemas/*.schema.json are the scantlings for the artifacts author,
  fact-checker, and the runner exchange. Each is referenced here per the
  Scantling agreement so an unreferenced entry never stands unnoticed.

  @contract
  Scenario Outline: A shared schema is valid JSON Schema
    Given the schema file "schemas/<schema>"
    When it is validated as a JSON Schema document
    Then it parses as valid JSON
    And its "$schema" field declares a JSON Schema draft

    Examples:
      | schema                   |
      | claims.schema.json       |
      | fact-check.schema.json   |
      | state.schema.json        |
      | plugin.schema.json       |
      | marketplace.schema.json  |
