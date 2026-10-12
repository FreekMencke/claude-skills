#!/usr/bin/env bash
# Symlink each skill in skills/ into ~/.claude/skills/ as a personal skill.
# Personal skills load in every session type that reads this home, including desktop WSL sessions,
# which don't load claude.ai account skills (claude-kb SKILL-050).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${HOME}/.claude/skills"
mkdir -p "$target"

for dir in "$repo"/skills/*/; do
  name="$(basename "$dir")"
  link="$target/$name"
  if [[ -e "$link" && ! -L "$link" ]]; then
    echo "skip $name: $link exists and is not a symlink" >&2
    continue
  fi
  ln -sfn "${dir%/}" "$link"
  echo "linked $name"
done
