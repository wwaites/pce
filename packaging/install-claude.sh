#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/artificial-org"
SKILL_DIR="${HOME}/.claude/skills"

mkdir -p "$PREFIX" "$SKILL_DIR"
rm -rf "$PREFIX/skills-core" "$PREFIX/schemas" "$PREFIX/templates" "$PREFIX/adapters"
cp -R "$ROOT/skills-core" "$ROOT/schemas" "$ROOT/templates" "$ROOT/adapters" "$PREFIX/"

for skill in "$ROOT"/adapters/claude/skills/*; do
  name="$(basename "$skill")"
  rm -rf "$SKILL_DIR/$name"
  cp -R "$skill" "$SKILL_DIR/$name"
done

printf 'Installed artificial-org support files to %s\n' "$PREFIX"
printf 'Installed Claude skills to %s\n' "$SKILL_DIR"
