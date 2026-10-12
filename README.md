# claude-skills

Source of truth for my personal Claude Code skills. The repo is a marketplace with two plugins (plugin names can't start
with `claude-`):

- **`freek-skills`** (repo root, `skills/`): skills that work on every surface. Installed on claude.ai, so they also
  reach chat, Cowork and every signed-in Claude Code session.
- **`freek-local-skills`** (`local-skills/`, its skills in `local-skills/skills/`): Claude Code-only skills that need this
  machine, such as a local clone or the session transcripts. Never installed on claude.ai. They may use Claude Code-only
  frontmatter (`disable-model-invocation`, `context`, `paths`).

A new skill goes in `local-skills/skills/` when it reads local files or uses Claude Code-only frontmatter, otherwise in
`skills/`. [Check](#check) covers the CI workflow and the trigger evals.

| Skill | Plugin | What it does |
|---|---|---|
| `roadmap-issues` | `freek-skills` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links |
| `parallel-code-orchestrator` | `freek-skills` | Split a large coding task or roadmap issue over parallel subagents |
| `refresh-md-files` | `freek-skills` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | `freek-skills` | Write or audit a skill, grounded in real material and published examples |
| `claude-kb-lookup` | `freek-local-skills` | Answer questions on using Claude efficiently from the claude-kb knowledge base, citing entry IDs. Runs as a forked Haiku subagent, so the index stays out of the caller's context |
| `handoff` | `freek-local-skills` | User-only (`/handoff`): write the session's state to the PR, issue or a scratch file, then `/clear` and continue from it |
| `token-audit` | `freek-local-skills` | User-only (`/token-audit`): measure token spend from the local transcripts and compare it with the 2026-10 baseline |

## Install

```bash
./install.sh
```

This symlinks each `skills/<name>` and `local-skills/skills/<name>` into `~/.claude/skills/<name>`, so edits here are
live in the next session, and removes links whose skill moved or was deleted. Run it again after adding, moving or
removing a skill, and after a pull that does. Use this on the machine where you edit the skills.

On another machine that should also get the local skills, install that plugin from the marketplace instead:
`claude plugin install freek-local-skills --marketplace FreekMencke/claude-skills` (git needs a GitHub credential for the
private repo; set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` without an SSH key). Never use both on one machine.

### claude.ai, chat, Cowork and other machines

The repo is also a marketplace, installed as a plugin on my claude.ai account (Customize › Plugins › Add marketplace
`FreekMencke/claude-skills`, then install `freek-skills` only, with **Sync automatically** on). The repo is private, so the
Claude GitHub App needs access to it. From there:

- Chat and Cowork load the skills as `freek-skills:<name>`. A merge to `main` reaches them without any upload.
- Every Claude Code session signed in to the account downloads the plugin as `freek-skills@synced`. On other machines
  that's the whole install. On the machine with `install.sh`, turn the synced copy off, or every skill is listed twice:
  `"freek-skills@synced": false` under `enabledPlugins` in `~/.claude/settings.json`.
- `version` is left out of `plugin.json` so updates track commits.

Skills in `skills/` keep to `name` and `description`: it's not checked that claude.ai accepts Claude Code-only
frontmatter (`when_to_use`, `paths`, `disable-model-invocation`). A skill that needs those goes in `local-skills/`.

Desktop sessions in WSL don't load claude.ai account skills (claude-kb `SKILL-050`), and it's not checked whether they
load synced plugins. The `install.sh` symlinks in the distro's `~/.claude/skills` do load there.

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

Trigger rates (runs that loaded the skill / skipped it, 3 runs per case, Opus 5.5, Claude Code 2.1.296):

| Skill | Should load | Near miss skipped | Date |
|---|---|---|---|
| `roadmap-issues` | 9/9 | 9/9 | 2026-10-12 |
| `parallel-code-orchestrator` | 9/9 | 9/9 | 2026-10-12 |
| `refresh-md-files` | 9/9 | 9/9 | 2026-10-12 |
| `skill-workshop` | 9/9 | 9/9 | 2026-10-12 |
| `claude-kb-lookup` | 9/9 | 9/9 | 2026-10-12 |
| `roadmap-issues` after #3 (5 should-load, 4 near-miss cases) | 15/15 | 12/12 | 2026-10-12 |
| `roadmap-issues` `loads-4`, `loads-5` (single cross-repo follow-up) after #3; `loads-4` was 0/3 before | 6/6 | | 2026-10-12 |
| `refresh-md-files` after #3 (4 + 4 cases) | 12/12 | 12/12 | 2026-10-12 |
| `skill-workshop` after #3 (4 + 4 cases) | 12/12 | 12/12 | 2026-10-12 |
| `parallel-code-orchestrator` after #4 (trigger-only description) | 9/9 | 9/9 | 2026-10-12 |
| `claude-kb-lookup` after #20 (new claude-kb topics; 11 + 5 cases) | 33/33 | 15/15 | 2026-10-12 |

Add a row with the new date when you rerun after a change, and keep the old rows for comparison.
