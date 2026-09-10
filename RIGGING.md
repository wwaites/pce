# Rigging

Project tooling values for Shipshape roles. Values only, not procedure.
Procedure lives in the skills. Every role reads this on open.

## Stack

- language: python
- runtime: python3
- packageManager: nix

## Directories

- implementation: packaging
- specs:
- verification:
- assets: skills-core
- assets: templates
- assets: adapters
- scantlings: schemas
- scantlings: scantlings/verification-conformance.json

## Commands

- discover:
- focused:
- broad:
- coverage: none
- step-usage:
- plank-inventory: `rg -n '@planks(-provisional)?\(' packaging`
- typecheck: none
- lint: none
- conformance: `python3 packaging/sync-adapters.py --check`

## Perturbation

- message: `PERTURBATION: consider current durable context; remove when fixed`
- perturb: `raise RuntimeError("PERTURBATION: consider current durable context; remove when fixed")`

## Tiers

- default: @logic
- sandbox: none
- policy: @logic: none, pure local, no external accounts
- weather: none
- runrecord: .shipshape/wake/run-record.jsonl

## Dependencies

- policy: locked
- dependency: behave

## Outbound

- outbound: origin/main
- ship: `git push origin main`
- verify: `git fetch origin main && test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"`
