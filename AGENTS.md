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

This repository is itself a skill pack, not an application: `skills-core/`, `templates/`, and `adapters/` are the shipped product content, and `packaging/` holds the only custom code (`run_loop.py`, `sync-adapters.py`, and the two install scripts). The Python stack carries no package manifest because the code has zero external dependencies; Nix (`flake.nix` / `flake.lock`) is the project's package manager, pinning the `python3` interpreter and the checked build.

`RIGGING.md` carries several required slots blank: `specs`, `verification`, `focused`, `discover`, `step-usage`, and `broad`. No Gherkin runner has been selected for this Python project (candidates include `behave`, `pytest-bdd`, and `radish`), and per the Shipwright skill that selection is a Captain-and-user dependency decision, not one Shipwright makes unilaterally. Resolve it with the user, record the choice under `## Dependencies` in `RIGGING.md`, and dispatch Shipwright to install the runner and complete the blocked slots.
