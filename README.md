# claude-skills

Claude Code skills, published as a plugin marketplace.

## Install

```bash
claude plugin marketplace add FreekMencke/claude-skills
claude plugin install freek-skills@freek-skills
claude plugin install freek-local-skills@freek-skills   # Claude Code only
```

On claude.ai: Customize › Plugins › Add marketplace `FreekMencke/claude-skills`, then install `freek-skills`.

## Skills

| Skill | What it does |
|---|---|
| `roadmap-issues` | Plan work as a GitHub roadmap issue with ordered sub-issues |
| `parallel-code-orchestrator` | Split a large coding task over parallel subagents |
| `refresh-md-files` | Find stale, ambiguous or missing docs |
| `skill-workshop` | Write or audit a skill |
| `research` | Answer a question with exact quotes, re-checked sources and tested claims |
| `tech-debt-audit` | Ranked technical-debt audit of a codebase |
| `angular-conventions` | Opinionated Angular rules on top of `angular-developer` |
| `angular-developer` | Angular's official skill, mirrored weekly |
| `handoff` * | Save the session's state, `/clear`, and continue from it |
| `token-audit` * | Measure token spend from your local transcripts |
| `seo-audit` * | Read-only technical SEO audit of a site ([data setup](local-skills/skills/seo-audit/references/data-sources.md#giving-a-session-the-data-for-the-user)) |

\* `freek-local-skills`, Claude Code only. `handoff` and `token-audit` run as slash commands, such as
`/freek-local-skills:handoff`.

## License

[MIT](LICENSE). `skills/angular-developer/` is Angular's, under its own MIT license (see its `NOTICE`).
