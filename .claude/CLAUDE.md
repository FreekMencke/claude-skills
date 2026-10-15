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
  from a worktree, it links every skill into that worktree. It symlinks each skill into `~/.claude/skills/`, so edits
  are live in the next session (desktop WSL sessions load these links, not claude.ai account skills; checked
  2026-10-14). Don't also install the plugins from the marketplace on that machine.
- `freek-skills` is installed on the owner's claude.ai account with Sync automatically on: a merge to `main` reaches
  chat and Cowork, and signed-in Claude Code sessions get it as `freek-skills@synced`. On the `install.sh` machine keep
  `"freek-skills@synced": false` under `enabledPlugins` in `~/.claude/settings.json`, or every skill is listed twice.
- New skill: add `loads-*` and `skips-*` trigger cases under `evals/<skill>/` or `local-skills/evals/<skill>/`.
- `skills/angular-developer/` is Angular's skill, mirrored weekly by `.github/workflows/sync-angular-skill.yml`:
  don't edit it or add trigger evals for it (README "angular-developer"). The workflow needs the repo setting Actions ›
  General › "Allow GitHub Actions to create and approve pull requests", and starts `validate.yml` on its PR itself (a PR
  opened with `GITHUB_TOKEN` starts no `pull_request` run). Run it by hand: `gh workflow run sync-angular-skill.yml`.
- After changing a description: run that skill's trigger evals (README "Trigger evals"; `--tag <skill>` limits cost)
  and replace that skill's row in the README results table; the before/after goes in the PR description.
