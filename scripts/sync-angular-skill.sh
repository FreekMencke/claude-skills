#!/usr/bin/env bash
# Mirror Angular's official angular-developer skill into skills/angular-developer/, byte for byte except the SKILL.md
# frontmatter, which keeps to name and description (scripts/check-frontmatter.py). Upstream's license and author move
# to NOTICE. .github/workflows/sync-angular-skill.yml runs this weekly.
#
#   sync-angular-skill.sh CHECKOUT    CHECKOUT is a clone of https://github.com/angular/skills
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="${1:?usage: sync-angular-skill.sh ANGULAR_SKILLS_CHECKOUT}/angular-developer"
dest="$repo/skills/angular-developer"

# Upstream has no LICENSE file: the frontmatter is the license. Stop rather than mirror it without one.
license="$(sed -n '2,/^---$/s/^license:[[:space:]]*//p' "$src/SKILL.md")"
author="$(sed -n '2,/^---$/s/^[[:space:]]*author:[[:space:]]*//p' "$src/SKILL.md")"
if [[ -z "$license" || -z "$author" ]]; then
  echo "$src/SKILL.md has no license or metadata.author in its frontmatter: check upstream's license" >&2
  exit 1
fi

rm -rf "$dest"
cp -R "$src" "$dest"

# Keep the top-level keys name and description, with their continuation lines.
awk '
  NR == 1 && /^---$/ { fm = 1; print; next }
  fm && /^---$/      { fm = 0; print; next }
  fm && /^[^ \t]/    { keep = /^(name|description):/ }
  !fm || keep
' "$src/SKILL.md" > "$dest/SKILL.md"

cat > "$dest/NOTICE" <<EOF
This folder mirrors angular-developer, Angular's official agent skill:
https://github.com/angular/skills/tree/main/angular-developer, generated from skills/dev-skills/ in
https://github.com/angular/angular.

License: $license. $author.
Upstream states both in the skill's frontmatter (license, metadata.author). This copy drops those keys, because
skills/ keeps to name and description; every other byte is upstream's.

.github/workflows/sync-angular-skill.yml writes this folder (scripts/sync-angular-skill.sh). Don't edit it here: the
next sync overwrites it. Fixes go upstream to angular/angular; house rules go in a skill of their own.
EOF
