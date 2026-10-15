# claude-skills

Freek Mencke's Claude Code skills, published as a plugin marketplace with two plugins (plugin names can't start with
`claude-`):

- **`freek-skills`** (repo root, `skills/`): skills that work on every surface: Claude Code, and claude.ai chat and
  Cowork when installed there.
- **`freek-local-skills`** (`local-skills/`, its skills in `local-skills/skills/`): Claude Code-only skills. Some read
  local files (the session transcripts); others rely on Claude Code's slash commands, tools or frontmatter
  (`disable-model-invocation`, `context`, `disallowed-tools`, `paths`). Don't install it on claude.ai.

| Skill | Plugin | What it does |
|---|---|---|
| `roadmap-issues` | `freek-skills` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links |
| `parallel-code-orchestrator` | `freek-skills` | Split a large coding task or roadmap issue over parallel subagents |
| `refresh-md-files` | `freek-skills` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | `freek-skills` | Write or audit a skill, grounded in real material and published examples |
| `tech-debt-audit` | `freek-skills` | Read-only technical-debt audit of a codebase in six phases, each checked by a reviewer subagent, ending in a ranked remediation roadmap |
| `angular-conventions` | `freek-skills` | An opinionated set of Angular rules on top of `angular-developer`: templates, layers, signal stores, failure states, routes and page meta, SSR on a custom Express server, tests and Tailwind. A repo's `CLAUDE.md` overrides it |
| `angular-developer` | `freek-skills` | Angular's official skill, mirrored weekly; don't edit here ([below](#angular-developer)) |
| `handoff` | `freek-local-skills` | User-only (`/handoff`): write the session's state to the PR, issue or a scratch file, then `/clear` and continue from it. Local because it's built on `/clear`, `/rewind` and `/resume` |
| `token-audit` | `freek-local-skills` | User-only (`/token-audit`): measure token spend from the local transcripts and compare it with a baseline saved on that machine |
| `seo-audit` | `freek-local-skills` | Read-only technical SEO audit of a site, from the server HTML a crawler gets, ranked by Search Console data when the session can reach it. Local because it runs from the app's repo, uses `disallowed-tools` to stay read-only, and checks pages in a local browser |

## Install

Claude Code:

```bash
claude plugin marketplace add FreekMencke/claude-skills
claude plugin install freek-skills@freek-skills
claude plugin install freek-local-skills@freek-skills
```

The marketplace is named `freek-skills`, like its first plugin. Neither plugin has a `version`, so an update follows the
latest commit.

claude.ai (chat and Cowork): Customize › Plugins › Add marketplace `FreekMencke/claude-skills`, then install
`freek-skills` only. Skills load there as `freek-skills:<name>`.

Setup a skill needs:

- `token-audit` keeps its baseline (offered on the first run) and the config changes to judge in
  `~/.claude/token-audit/`.
- `seo-audit` uses Search Console, a PageSpeed Insights key, GA4, logs and a browser when the session has them; the last
  section of `local-skills/skills/seo-audit/references/data-sources.md` says how to set each one up.
- `roadmap-issues` and `parallel-code-orchestrator` use `gh`, signed in to GitHub.

## License

[MIT](LICENSE). `skills/angular-developer/` is Angular's, under its own MIT license (its `NOTICE`).

## angular-developer

`skills/angular-developer/` is Angular's official agent skill from [angular/skills](https://github.com/angular/skills),
which is generated from `skills/dev-skills/` in angular/angular and follows its `main`.
`.github/workflows/sync-angular-skill.yml` copies it every Monday with `scripts/sync-angular-skill.sh`: byte for byte,
except that the `SKILL.md` frontmatter keeps to `name` and `description` and upstream's license and author go to
`NOTICE`. When the folder changed, it opens or updates one PR from `sync/angular-developer` and starts `validate.yml` on
it, because a PR opened with `GITHUB_TOKEN` starts no `pull_request` run. It needs the repo setting Actions › General ›
"Allow GitHub Actions to create and approve pull requests". Run it by hand with
`gh workflow run sync-angular-skill.yml`.

Don't edit the folder: the next sync overwrites it. House rules go in `angular-conventions`. It has no trigger evals,
because its description is upstream's.

## Maintaining these skills

A new skill goes in `local-skills/skills/` when it reads local files, relies on Claude Code slash commands or tools, or
uses Claude Code-only frontmatter, otherwise in `skills/`. [Check](#check) covers the CI workflow and the trigger evals.

On the machine where the skills are edited, link them instead of installing the plugins:

```bash
./install.sh
```

This symlinks each `skills/<name>` and `local-skills/skills/<name>` into `~/.claude/skills/<name>`, so edits here are
live in the next session, and removes links whose skill moved or was deleted. Run it again after adding, moving or
removing a skill, and after a pull that does. Never combine it with a marketplace install of the same plugin on one
machine.

The marketplace is also installed on the owner's claude.ai account, with **Sync automatically** on:

- Chat and Cowork get a merge to `main` without any upload.
- Every Claude Code session signed in to the account downloads `freek-skills` as `freek-skills@synced`. On other
  machines that's the whole install. On the machine with `install.sh`, turn the synced copy off, or every skill is
  listed twice: `"freek-skills@synced": false` under `enabledPlugins` in `~/.claude/settings.json`.

Skills in `skills/` keep to `name` and `description`: it's not checked that claude.ai accepts Claude Code-only
frontmatter (`when_to_use`, `paths`, `disable-model-invocation`). A skill that needs those goes in `local-skills/`.

Desktop sessions in WSL didn't load claude.ai account skills (checked 2026-10-14), and it's not
checked whether they load synced plugins. The `install.sh` symlinks in the distro's `~/.claude/skills` do load there.

## Check

CI (`.github/workflows/validate.yml`) runs `claude plugin validate` on `.` and on `local-skills` on pushes to `main` and on PRs, and fails on any
error or warning except the missing `version`, which is left out on purpose so installs track commits (that's also why
it doesn't use `--strict`). Locally:

```bash
claude plugin validate .
claude plugin validate local-skills
```

The root check covers the marketplace and `freek-skills`, but not the skills inside `local-skills/`.

It doesn't flag unknown frontmatter keys, so `scripts/check-frontmatter.py` checks that each `skills/*/SKILL.md` keeps
to `name` and `description` (both present, nothing else). CI runs it, and a `PostToolUse` hook in `.claude/settings.json`
runs it after Claude edits one of those files in a session here. Locally:

```bash
python3 scripts/check-frontmatter.py
```

### Trigger evals

`evals/<skill>/` and `local-skills/evals/<skill>/` hold trigger cases for `claude plugin eval`: per skill, `loads-*` prompts that should load it and
`skips-*` near misses that shouldn't, mostly taken from a sibling skill's territory. Each case has one free
`tool_used: Skill` grader. Run them by hand after changing a description, not in CI: every run is a model call on your
plan (about $0.08 each, so about $8 for the suite at 3 runs per case).

```bash
claude plugin eval . --ablation none --model claude-opus-5-5 --no-publish -j 4 --threshold 0
claude plugin eval local-skills --ablation none --model claude-opus-5-5 --no-publish -j 4 --threshold 0
```

- `--ablation none`: the no-plugin arm says nothing about triggering and doubles the cost.
- `--model`: pin it, so a model change isn't read as a description regression. Add `--case 'refresh-md-files-*'` or
  `--tag <skill>` to run one skill.
- Runs are isolated: only the skills of the plugin under test compete, so the two plugins don't see each other. Overlap with skills from other plugins (`claude-md-improver`,
  `skill-creator`) doesn't show up here.
- Results go to `evals/results/` and `local-skills/evals/results/`, which are ignored.

Trigger rates of the latest run per skill (runs that loaded the skill / skipped it, 3 runs per case, Opus 5.5):

| Skill | Cases (load + near miss) | Should load | Near miss skipped | Claude Code | Date |
|---|---|---|---|---|---|
| `roadmap-issues` | 5 + 5 | 15/15 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14 |
| `parallel-code-orchestrator` | 3 + 3 | 9/9 | 9/9 | 2.1.296 | 2026-10-12 |
| `refresh-md-files` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14 |
| `skill-workshop` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14 |
| `seo-audit` | 4 + 4 | 12/12 | 12/12 | 2.1.296 | 2026-10-13 |
| `tech-debt-audit` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-14 |
| `angular-conventions` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-14 |

When you rerun after a change, replace that skill's row and put the before/after in the PR description; git history
keeps the old numbers.
