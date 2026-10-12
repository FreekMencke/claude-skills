# claude-skills

Source of truth for my personal Claude Code skills. The repo is laid out as a skills-dir plugin (`freek-skills`;
plugin names can't start with `claude-`) and a marketplace, so `claude plugin validate .` and `claude plugin eval .` work
on it. [Check](#check) covers the CI workflow and the trigger evals in `evals/`.

| Skill | What it does |
|---|---|
| `roadmap-issues` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links |
| `parallel-code-orchestrator` | Split a large coding task or roadmap issue over parallel subagents |
| `refresh-md-files` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | Write or audit a skill, grounded in real material and published examples |
| `claude-kb-lookup` | Answer questions on using Claude efficiently from the claude-kb knowledge base, citing entry IDs |

## Install

```bash
./install.sh
```

This symlinks each `skills/<name>` into `~/.claude/skills/<name>`, so edits here are live in the next session. Run it
again after adding a skill. Use this on the machine where you edit the skills.

### claude.ai, chat, Cowork and other machines

The repo is also a marketplace, installed as a plugin on my claude.ai account (Customize › Plugins › Add marketplace
`FreekMencke/claude-skills`, then install `freek-skills`, with **Sync automatically** on). The repo is private, so the
Claude GitHub App needs access to it. From there:

- Chat and Cowork load the skills as `freek-skills:<name>`. A merge to `main` reaches them without any upload.
- Every Claude Code session signed in to the account downloads the plugin as `freek-skills@synced`. On other machines
  that's the whole install. On the machine with `install.sh`, turn the synced copy off, or every skill is listed twice:
  `"freek-skills@synced": false` under `enabledPlugins` in `~/.claude/settings.json`.
- `version` is left out of `plugin.json` so updates track commits.
- `claude-kb-lookup` also reaches chat and Cowork, where it has no claude-kb clone to read. It only costs a listing line.

Don't add Claude Code-only frontmatter (`when_to_use`, `paths`, `disable-model-invocation`) to skills in this plugin
until it's checked that claude.ai accepts it: keep to `name` and `description`.

Desktop sessions in WSL don't load claude.ai account skills (claude-kb `SKILL-050`), and it's not checked whether they
load synced plugins. The `install.sh` symlinks in the distro's `~/.claude/skills` do load there.

## Check

CI (`.github/workflows/validate.yml`) runs `claude plugin validate .` on pushes to `main` and on PRs, and fails on any
error or warning except the missing `version`, which is left out on purpose so installs track commits (that's also why
it doesn't use `--strict`). Locally:

```bash
claude plugin validate .
```

It doesn't flag unknown frontmatter keys, so check by hand that the skills keep to `name` and `description`.

### Trigger evals

`evals/<skill>/` holds trigger cases for `claude plugin eval`: per skill, `loads-*` prompts that should load it and
`skips-*` near misses that shouldn't, mostly taken from a sibling skill's territory. Each case has one free
`tool_used: Skill` grader. Run them by hand after changing a description, not in CI: every run is a model call on your
plan (about $0.08 each, so about $8 for the suite at 3 runs per case).

```bash
claude plugin eval . --ablation none --model claude-opus-5-5 --no-publish -j 4 --threshold 0
```

- `--ablation none`: the no-plugin arm says nothing about triggering and doubles the cost.
- `--model`: pin it, so a model change isn't read as a description regression. Add `--case 'refresh-md-files-*'` or
  `--tag <skill>` to run one skill.
- Runs are isolated: only this plugin's skills compete. Overlap with skills from other plugins (`claude-md-improver`,
  `skill-creator`) doesn't show up here.
- Results go to `evals/results/`, which is ignored.

Trigger rates (runs that loaded the skill / skipped it, 3 runs per case, Opus 5.5, Claude Code 2.1.296):

| Skill | Should load | Near miss skipped | Date |
|---|---|---|---|
| `roadmap-issues` | 9/9 | 9/9 | 2026-10-12 |
| `roadmap-issues` `loads-4` (single cross-repo follow-up) | 0/3 | | 2026-10-12 |
| `parallel-code-orchestrator` | 9/9 | 9/9 | 2026-10-12 |
| `refresh-md-files` | 9/9 | 9/9 | 2026-10-12 |
| `skill-workshop` | 9/9 | 9/9 | 2026-10-12 |
| `claude-kb-lookup` | 9/9 | 9/9 | 2026-10-12 |
| `roadmap-issues` after #3 (5 should-load, 4 near-miss cases) | 15/15 | 12/12 | 2026-10-12 |
| `roadmap-issues` `loads-4`, `loads-5` (single cross-repo follow-up) after #3 | 6/6 | | 2026-10-12 |
| `refresh-md-files` after #3 (4 + 4 cases) | 12/12 | 12/12 | 2026-10-12 |
| `skill-workshop` after #3 (4 + 4 cases) | 12/12 | 12/12 | 2026-10-12 |
| `parallel-code-orchestrator` after #4 (trigger-only description) | 9/9 | 9/9 | 2026-10-12 |

Add a row with the new date when you rerun after a change, and keep the old rows for comparison.
