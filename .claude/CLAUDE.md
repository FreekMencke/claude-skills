# claude-skills

Marketplace with two plugins. README.md is for people installing them; working here is below.

- Each plugin has its own folder under `plugins/`, and the repo root is only the marketplace. Keep it that way: the
  claude.ai marketplace sync skips a plugin whose folder holds another `plugin.json` (it skipped `freek-skills` while
  its root was `./`, around `local-skills/`), which `claude plugin validate` doesn't catch. It also strips keys outside
  its manifest schema, such as `$schema`, with a warning.
- `plugins/freek-skills/skills/` (`freek-skills`, synced to claude.ai): frontmatter is `name` and `description` only,
  because a claude.ai upload fails on any key outside the Agent Skills spec (code.claude.com/docs/en/skills, "Using
  skill frontmatter outside Claude Code"), and it's not checked whether a marketplace sync does the same. `validate`
  doesn't flag unknown keys, so `scripts/check-frontmatter.py` enforces it (CI and a `PostToolUse` hook).
- `plugins/freek-local-skills/skills/` (`freek-local-skills`, Claude Code only): skills that read local files, rely on
  Claude Code slash commands or tools, or need Claude Code-only frontmatter (`disable-model-invocation`, `context`,
  `disallowed-tools`, `paths`).
- No `version` in either `plugin.json`, on purpose (installs track commits); don't add one for the validate warning.
  It's also why CI doesn't use `--strict`; any other warning fails CI.
- Don't write `$0` in a skill: Claude Code replaces it with the first argument. In awk, use `$(0)`.
- Verify (CI runs the same on pushes to `main` and on PRs): `claude plugin validate` on `.` (the marketplace),
  `plugins/freek-skills` and `plugins/freek-local-skills`, and `python3 scripts/check-frontmatter.py`.
- `main` is protected by the repo ruleset `main`, without bypass: changes land through a PR, squash only, once CI's
  `validate` passes (no approvals, no up-to-date requirement); force pushes and deletion are blocked. A direct push to
  `main` fails. If CI itself breaks, the owner can switch the ruleset off in Settings › Rules.
- The owner's Claude Code installs both plugins from this marketplace (`FreekMencke/claude-skills`, `autoUpdate: true`
  under `extraKnownMarketplaces` in `~/.claude/settings.json`), so a merge to `main` reaches sessions after they
  restart. To try a skill before it's merged: `claude --plugin-dir plugins/<plugin>` from the worktree.
- `freek-skills` is installed on the owner's claude.ai account with Sync automatically on: a merge to `main` reaches
  chat and Cowork. Signed-in Claude Code sessions also get it as `freek-skills@synced`; the marketplace install of the
  same name takes precedence, so it isn't listed twice.
- New skill: add `loads-*` and `skips-*` trigger cases under `plugins/<plugin>/evals/<skill>/`: prompts that should load
  it, and near misses (mostly from a sibling skill's territory) that shouldn't. Each case has one `tool_used: Skill`
  grader.
- `plugins/freek-skills/skills/angular-developer/` is Angular's skill from `angular/skills`, mirrored every Monday
  through a PR by `.github/workflows/sync-angular-skill.yml`: don't edit it (the next sync overwrites it) or add trigger
  evals for it (its description is upstream's); house rules go in `angular-conventions`. It's byte for byte except the
  frontmatter, cut to `name` and `description`; upstream's license and author go to its `NOTICE`. The workflow needs the
  repo setting Actions › General › "Allow GitHub Actions to create and approve pull requests", and starts `validate.yml`
  on its PR itself (a PR opened with `GITHUB_TOKEN` starts no `pull_request` run). Run it by hand: `gh workflow run
  sync-angular-skill.yml`.
- After changing a description: run that skill's trigger evals, by hand (3 model calls per case; about 2 minutes per
  skill at `-j 4`, measured 2026-10-15), never in CI. `claude plugin eval plugins/<plugin> --ablation none --model
  claude-opus-5-5 --no-publish -j 4 --threshold 0 --tag <skill>`: the no-plugin arm says nothing about triggering and
  doubles the cost; a pinned model keeps a model change from reading as a regression; only the last `--case` counts.
  Only the plugin under test's skills compete. Results go to the ignored `plugins/<plugin>/evals/results/`. Then replace
  that skill's row in `plugins/freek-skills/evals/RESULTS.md` (both plugins); the before/after goes in the PR
  description.
