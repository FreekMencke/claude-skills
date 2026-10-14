# claude-skills

Marketplace with two plugins; README.md has the full layout, install and eval details. This file is in
`.claude/` because `claude plugin validate` warns about a `CLAUDE.md` at the plugin root, and CI fails on that warning.

- `skills/` (`freek-skills`, synced to claude.ai): frontmatter is `name` and `description` only;
  `scripts/check-frontmatter.py` enforces it (CI and a `PostToolUse` hook).
- `local-skills/skills/` (`freek-local-skills`, Claude Code only): skills that read local files, rely on Claude Code
  slash commands or tools, or need Claude Code-only frontmatter (`disable-model-invocation`, `context`, `paths`).
- No `version` in either `plugin.json`, on purpose (installs track commits); don't add one for the validate warning.
- Don't write `$0` in a skill: Claude Code replaces it with the first argument. In awk, use `$(0)`.
- Verify: `claude plugin validate .`, `claude plugin validate local-skills` and `python3 scripts/check-frontmatter.py`.
- After adding, moving or removing a skill: `./install.sh` in the main checkout, once the change is pulled there. Run
  from a worktree, it links every skill into that worktree.
- New skill: add `loads-*` and `skips-*` trigger cases under `evals/<skill>/` or `local-skills/evals/<skill>/`.
- `skills/angular-developer/` is Angular's skill, mirrored weekly by `.github/workflows/sync-angular-skill.yml`:
  don't edit it or add trigger evals for it (README "angular-developer").
- After changing a description: run that skill's trigger evals (README "Trigger evals"; `--tag <skill>` limits cost)
  and replace that skill's row in the README results table; the before/after goes in the PR description.
