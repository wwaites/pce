# Agent Instructions

This project uses Shipshape, a context-isolated spec-driven workflow for coding agents.

Agent opening this project: ensure Shipshape is installed, then load the `shipshape` skill (`shipshape:shipshape` under the plugin channel) and follow its routing before other work. Decide how to involve the human per your configured preferences.

Tooling values such as stack, directories, and commands live in `RIGGING.md`.

Install with the open skills CLI, which works across most agent runtimes:

```bash
npx skills add dmytri/shipshape --skill '*'
```

If your runtime supports the open-plugin format, such as Claude Code or Cursor, install the experimental plugin build instead:

```bash
npx plugins add dmytri/shipshape
```

Update Shipshape at a voyage boundary with `npx skills update` for the skills install, or re-run `npx plugins add dmytri/shipshape` for the plugin build.

## Project notes

This repository is itself a skill pack, not an application: `skills-core/`, `templates/`, and `adapters/` are the shipped product content, and `packaging/` holds the only custom code (`run_loop.py`, `sync-adapters.py`, and the two install scripts). The Python stack carries no package manifest because the code has zero external dependencies; Nix (`flake.nix` / `flake.lock`) is the project's package manager, pinning the `python3` interpreter and the checked build. `flake.nix` also carries a `devShells.default` that provides `behave` and `coverage`, the two fitted Gherkin-runner and coverage dependencies; run verification commands through `nix develop --command ...` as `RIGGING.md` does.

Every packaging seam carries `@planks(...)` naming the step-definition pattern that binds it. `packaging/run_loop.py`'s role-dispatch functions (`run_claude`, `run_opencode`, `dispatch`, `run_author`, `run_archivist`, `run_fact_checker`, `run_critic`, and `main`'s gate loop) call a real `claude` or `opencode` CLI; their scenario is fitted under the `@sandbox` tier in `features/run-loop.feature` and dispatches a real `claude` CLI subprocess, opt-in only through the `broad-sandbox` and `coverage-sandbox` commands, never part of the default `@logic` sweep. One `@conformance @captain` scenario remains in `features/methodology.feature` (the plank-coverage rule) awaiting Captain promotion.
