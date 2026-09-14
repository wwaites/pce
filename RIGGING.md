# Rigging

Project tooling values for Shipshape roles. Values only, not procedure.
Procedure lives in the skills. Every role reads this on open.

## Stack

- language: python
- runtime: python3
- packageManager: nix

## Directories

- implementation: packaging
- specs: features
- verification: features/steps
- assets: skills-core
- assets: templates
- assets: adapters
- scantlings: schemas
- scantlings: scantlings/verification-conformance.json

## Commands

- discover: `nix develop --command behave --dry-run --no-summary --tags "not @captain and not @shipwright" features`
- focused: `nix develop --command python3 -c "import re, subprocess, sys; files = {}; [files.setdefault(r.split('.feature:', 1)[0] + '.feature', []).append(r.split('.feature:', 1)[1]) for r in sys.argv[1:]]; args = ['behave', '--tags', 'not @captain and not @shipwright']; [args.extend(['-n', '^' + re.escape(n) + r'( -- @[0-9]+\.[0-9]+ )?\$']) for v in files.values() for n in v]; args.extend(files.keys()); sys.exit(subprocess.call(args))" {scenario}`
- broad: `nix develop --command behave --no-summary --tags "not @sandbox and not @captain and not @shipwright" features`
- broad-sandbox: `nix develop --command behave --no-summary --tags "@sandbox and not @captain and not @shipwright" features`
- coverage: `nix develop --command bash -c 'coverage run --branch --source=packaging -m behave --no-summary --tags "not @sandbox and not @captain and not @shipwright" features && coverage report -m'`
- coverage-sandbox: `nix develop --command bash -c 'coverage run --branch --source=packaging -m behave --no-summary --tags "@sandbox and not @captain and not @shipwright" features && coverage report -m'`
- step-usage: `nix develop --command behave --dry-run --no-summary -f steps.usage features`
- plank-inventory: `rg -n '@planks\(|@planks-provisional\(' packaging`
- typecheck: none
- lint: `nix develop --command ruff check packaging`
- conformance: `python3 packaging/sync-adapters.py --check`

## Perturbation

- message: `PERTURBATION: consider current durable context; remove when fixed`
- perturb: `raise RuntimeError("PERTURBATION: consider current durable context; remove when fixed")`

## Tiers

- default: @logic
- sandbox: @sandbox
- policy: @logic: none, pure local, no external accounts
- policy: @sandbox: real claude or opencode CLI subprocess with live runtime credentials required; opt-in only, never part of the default @logic sweep
- weather: none
- runrecord: .shipshape/wake/run-record.jsonl

## Dependencies

- policy: locked
- dependency: behave
- dependency: coverage
- dependency: ruff

## Outbound

- outbound: origin/main
- ship: `git push origin main`
- verify: `git fetch origin main && test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"`
