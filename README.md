# claude-skills

Claude Code skills by Freek Mencke, published as a plugin marketplace: GitHub roadmaps and parallel subagents, doc and
tech-debt audits, skill writing, Angular conventions, and SEO and token-spend audits.

## Install

```bash
claude plugin marketplace add FreekMencke/claude-skills
claude plugin install freek-skills@freek-skills
claude plugin install freek-local-skills@freek-skills
```

- **`freek-skills`** works wherever skills run. For claude.ai chat and Cowork: Customize › Plugins › Add marketplace
  `FreekMencke/claude-skills`, then install `freek-skills`.
- **`freek-local-skills`** is for Claude Code only: its skills read local files or rely on Claude Code's slash commands,
  tools or frontmatter. Don't install it on claude.ai.
- Neither plugin has a `version`, so an update follows the latest commit on `main`.

Skills load when a task matches their description. The user-only ones run as slash commands, such as
`/freek-local-skills:handoff`.

## Skills

### `freek-skills`

| Skill | What it does |
|---|---|
| `roadmap-issues` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links, or open a follow-up issue in another repo |
| `parallel-code-orchestrator` | Split a large coding task or a roadmap issue over parallel subagents |
| `refresh-md-files` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | Write or audit a skill, grounded in real material and published examples |
| `tech-debt-audit` | Read-only technical-debt audit in six phases, each checked by a reviewer subagent, ending in a ranked remediation roadmap |
| `angular-conventions` | An opinionated set of Angular rules on top of `angular-developer`: templates, layers, signal stores, failure states, routes and page meta, SSR on a custom Express server, tests and Tailwind. A repo's `CLAUDE.md` overrides it |
| `angular-developer` | Angular's official skill from [angular/skills](https://github.com/angular/skills), mirrored weekly |

### `freek-local-skills`

| Skill | What it does |
|---|---|
| `handoff` | User-only: write the session's state to the PR, issue or a scratch file, so you can `/clear` and continue from it |
| `token-audit` | User-only: measure token spend from the local session transcripts and compare it with a baseline saved on that machine |
| `seo-audit` | Read-only technical SEO audit of a site, from the server HTML a crawler gets, ranked by Search Console data when the session can reach it |

### What some skills need

- `roadmap-issues` and `parallel-code-orchestrator`: `gh`, signed in to GitHub.
- `token-audit`: keeps its baseline (offered on the first run) and the config changes to judge in
  `~/.claude/token-audit/`.
- `seo-audit`: Search Console, a PageSpeed Insights key, GA4, logs and a browser, each used when the session has it.
  [Giving a session the data](local-skills/skills/seo-audit/references/data-sources.md#giving-a-session-the-data-for-the-user)
  says how to set each one up.

## Development

A skill goes in `local-skills/skills/` when it reads local files, relies on Claude Code slash commands or tools, or uses
Claude Code-only frontmatter (`disable-model-invocation`, `context`, `disallowed-tools`, `paths`); otherwise in
`skills/`. Skills in `skills/` keep to `name` and `description`, because they also run on claude.ai and it's not
checked that claude.ai accepts the Claude Code-only keys.

### Check

CI (`.github/workflows/validate.yml`) runs these on pushes to `main` and on PRs:

```bash
claude plugin validate .
claude plugin validate local-skills
python3 scripts/check-frontmatter.py
```

- `validate` fails on any error or warning except the missing `version`, which is left out on purpose (it's also why CI
  doesn't use `--strict`). The root check covers the marketplace and `freek-skills`, not the skills in `local-skills/`.
- `validate` doesn't flag unknown frontmatter keys, so `check-frontmatter.py` checks that each `skills/*/SKILL.md` has
  `name` and `description` and nothing else. A `PostToolUse` hook in `.claude/settings.json` also runs it after Claude
  edits one of those files.

### Trigger evals

`evals/<skill>/` and `local-skills/evals/<skill>/` hold trigger cases for `claude plugin eval`: per skill, `loads-*`
prompts that should load it and `skips-*` near misses that shouldn't, mostly from a sibling skill's territory. Each case
has one `tool_used: Skill` grader. Run them by hand after changing a description, not in CI: each run is a model call
(about $0.08, so about $8 for the suite at 3 runs per case).

```bash
claude plugin eval . --ablation none --model claude-opus-5-5 --no-publish -j 4 --threshold 0
claude plugin eval local-skills --ablation none --model claude-opus-5-5 --no-publish -j 4 --threshold 0
```

- `--ablation none`: the no-plugin arm says nothing about triggering and doubles the cost.
- `--model`: pin it, so a model change isn't read as a description regression.
- `--tag <skill>` or `--case '<skill>-*'` runs one skill. Only the last `--case` counts, so pass one pattern.
- Only the skills of the plugin under test compete, so overlap with other plugins' skills doesn't show up here.
- Results go to `evals/results/` and `local-skills/evals/results/`, which git ignores.

Latest run per skill (runs that loaded the skill / skipped it, 3 runs per case, Opus 5.5):

| Skill | Cases (load + near miss) | Should load | Near miss skipped | Claude Code | Date |
|---|---|---|---|---|---|
| `roadmap-issues` | 5 + 5 | 15/15 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14; `loads-*` 2026-10-15 |
| `parallel-code-orchestrator` | 3 + 3 | 9/9 | 9/9 | 2.1.296 | 2026-10-12 |
| `refresh-md-files` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14 |
| `skill-workshop` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14; `skips-3` 2026-10-15 |
| `seo-audit` | 4 + 4 | 12/12 | 12/12 | 2.1.296 | 2026-10-13; `skips-4` 2026-10-15 |
| `tech-debt-audit` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-14 |
| `angular-conventions` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-14 |

After a rerun, replace that skill's row and put the before/after in the PR description; git history keeps the old
numbers.

### angular-developer

`skills/angular-developer/` is a copy of Angular's skill from [angular/skills](https://github.com/angular/skills), which
follows angular/angular's `main`. It's byte for byte, except that the frontmatter keeps to `name` and `description`;
upstream's license and author are in its `NOTICE`. `.github/workflows/sync-angular-skill.yml` refreshes it every Monday
through a PR. Don't edit the folder (the next sync overwrites it) or add trigger evals for it (its description is
upstream's); house rules go in `angular-conventions`.

## License

[MIT](LICENSE). `skills/angular-developer/` is Angular's, under its own MIT license (see its `NOTICE`).
