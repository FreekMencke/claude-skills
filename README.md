# claude-skills

Source of truth for my personal Claude Code skills. The repo is laid out as a skills-dir plugin (`freek-skills`;
plugin names can't start with `claude-`) and a marketplace, so `claude plugin validate .` and `claude plugin eval .` work
on it. [Check](#check) covers the CI workflow and the trigger evals in `evals/`.

| Skill | What it does |
|---|---|
| `roadmap-issues` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links |
| `parallel-code-orchestrator` | Split a large coding task over parallel subagents, then integrate, verify and review |
| `refresh-md-files` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | Write or audit a skill, grounded in real material and published examples |
| `claude-kb-lookup` | Answer questions on using Claude efficiently from the claude-kb knowledge base, citing entry IDs |

## Install

```bash
./install.sh
```

This symlinks each `skills/<name>` into `~/.claude/skills/<name>`, so edits here are live in the next session. Run it
again after adding a skill. Use this on the machine where you edit the skills.

### Other machines

The repo is also a marketplace. Install the plugin from it instead of cloning (Claude Code 2.1.275 or later):

```bash
CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1 claude plugin install freek-skills --marketplace FreekMencke/claude-skills
```

or, in a session:

```text
/plugin install freek-skills --marketplace FreekMencke/claude-skills
```

- The repo is private: git needs a stored credential (`gh auth login`, then `gh auth setup-git`). Set
  `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` in the environment when the machine has no GitHub SSH key, or in-session installs
  and updates fail.
- Skills are then named `freek-skills:<name>`, and `/freek-skills:roadmap-issues` runs one.
- Updates aren't automatic: run `claude plugin update freek-skills@freek-skills`, or turn on auto-update for the
  marketplace under **Marketplaces** in `/plugin`. `version` is left out of `plugin.json` so updates track commits.
- Don't combine this with `install.sh` on one machine, or every skill is listed twice.

Why not claude.ai only: desktop sessions in WSL don't load claude.ai account skills, although the files sync to
`~/.claude/skills/synced/` (claude-kb `SKILL-050`). Personal skills in the distro's `~/.claude/skills` do load there.

## claude.ai copies

Chat, Cowork and desktop Local sessions still get these skills from claude.ai. After changing a skill here, upload its
folder as a ZIP on claude.ai so the copies don't drift. Don't upload `claude-kb-lookup`: it reads a local clone of
claude-kb at `/home/fremen/repos/claude-kb` and has nothing to read on claude.ai. Synced skills only carry standard frontmatter (`name`,
`description`), so don't add Claude Code-only fields such as `when_to_use` or `paths` while claude.ai is a channel.

The terminal CLI lists each skill twice: once as a personal skill and once as `anthropic-skills:<name>`.
`syncClaudeAiSkills: false` in `~/.claude/settings.json` removes the second copy, but also every other account skill.

## Check

CI (`.github/workflows/validate.yml`) runs `claude plugin validate .` on pushes to `main` and on PRs, and fails on any
error or warning except the missing `version`, which is left out on purpose so installs track commits (that's also why
it doesn't use `--strict`). Locally:

```bash
claude plugin validate .
```

It doesn't flag unknown frontmatter keys, so check by hand that the uploaded skills keep to `name` and `description`.

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

Add a row with the new date when you rerun after a change, and keep the old rows for comparison.
