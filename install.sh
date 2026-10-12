#!/usr/bin/env bash
# Symlink each skill in skills/ and local-skills/skills/ into ~/.claude/skills/ as a personal skill.
# Personal skills load in every session type that reads this home, including desktop WSL sessions,
# which don't load claude.ai account skills (claude-kb SKILL-050).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${HOME}/.claude/skills"
mkdir -p "$target"

# Remove links into this repo whose skill moved or was deleted.
for link in "$target"/*; do
  if [[ -L "$link" && ! -e "$link" && "$(readlink "$link")" == "$repo"/* ]]; then
    rm "$link"
    echo "removed stale $(basename "$link")"
  fi
done

for dir in "$repo"/skills/*/ "$repo"/local-skills/skills/*/; do
  name="$(basename "$dir")"
  link="$target/$name"
  if [[ -e "$link" && ! -L "$link" ]]; then
    echo "skip $name: $link exists and is not a symlink" >&2
    continue
  fi
  ln -sfn "${dir%/}" "$link"
  echo "linked $name"
done
