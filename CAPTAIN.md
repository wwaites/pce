> STOP. Captain's notes: non-binding. Captain writes, Captain trims. Anyone else: close this file now.

# Captain Notes

Binding behaviour lives in `.feature` specs and referenced `assets/**`. History lives in git. These notes carry only what the next cycle needs.

## Environment

- This machine has Claude Code and opencode installed; Pi is not yet packaged under this project's Nix setup, and Codex's subagent/process-spawn capabilities are unconfirmed. Near-term runner work (`packaging/run_loop.py`) targets Claude Code and opencode only.
- Headless `claude -p` calls on this machine fail with "Credit balance is too low" if `ANTHROPIC_API_KEY` is set in the environment - that key's balance is exhausted. Prefix with `env -u ANTHROPIC_API_KEY` to fall back to the working claude.ai OAuth login.

## Named decisions

- 2026-09-14: Fixed RIGGING.md's `focused` command's Scenario Outline regex
  directly (Captain's authority at sea), rather than a third Shipwright
  dispatch. Two prior Shipwright passes (one full, one scoped to
  RIGGING.md/AGENTS.md) missed this exact defect via static review; it only
  surfaces by actually running the composed command against a live Outline
  reference, which QM did and root-caused precisely. Verified the fix myself
  by direct execution before committing to it: an Outline reference now
  selects all examples, a plain scenario reference still selects exactly one.

## Process note

Auto-memory (the `~/.claude/projects/.../memory/` mechanism) must not be used for this repo: it injects into every session touching this project directory regardless of role, including fresh QM/Crew/Boatswain subagent dispatches, which is exactly the bulkhead violation Article 7 forbids. Use this file for Captain-persistent notes instead - nothing auto-injects it, and `.rgignore` already excludes it from sweeps.
