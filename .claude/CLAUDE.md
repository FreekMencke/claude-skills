# claude-skills

Marketplace with two plugins; README.md has the full layout, install and eval details. This file is in
`.claude/` because `claude plugin validate` warns about a `CLAUDE.md` at the plugin root, and CI fails on that warning.

- `skills/` (`freek-skills`, synced to claude.ai): frontmatter is `name` and `description` only; CI doesn't flag other keys.
- `local-skills/skills/` (`freek-local-skills`, Claude Code only): skills that read local files or need Claude Code-only
  frontmatter (`disable-model-invocation`, `context`, `paths`).
- No `version` in either `plugin.json`, on purpose (installs track commits); don't add one for the validate warning.
- Don't write `$0` in a skill: Claude Code replaces it with the first argument. In awk, use `$(0)`.
- Verify: `claude plugin validate .` and `claude plugin validate local-skills`.
- After adding, moving or removing a skill: `./install.sh`.
- New skill: add `loads-*` and `skips-*` trigger cases under `evals/<skill>/` or `local-skills/evals/<skill>/`.
- After changing a description: run that skill's trigger evals (README "Trigger evals"; `--tag <skill>` limits cost)
  and add a dated row to the README results table, keeping old rows.
