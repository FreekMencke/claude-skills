# claude-skills

Source of truth for my personal Claude Code skills. The repo is laid out as a skills-dir plugin (`freek-skills`;
plugin names can't start with `claude-`), so `claude plugin validate --strict .` and `claude plugin eval .` work on it.

| Skill | What it does |
|---|---|
| `roadmap-issues` | Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links |
| `parallel-code-orchestrator` | Split a large coding task over parallel subagents, then integrate, verify and review |
| `refresh-md-files` | Audit `.md` docs for gaps, ambiguity and stale content |
| `skill-workshop` | Write or audit a skill, grounded in real material and published examples |

## Install

```bash
./install.sh
```

This symlinks each `skills/<name>` into `~/.claude/skills/<name>`, so edits here are live in the next session. Run it
again after adding a skill.

Why not claude.ai only: desktop sessions in WSL don't load claude.ai account skills, although the files sync to
`~/.claude/skills/synced/` (claude-kb `SKILL-050`). Personal skills in the distro's `~/.claude/skills` do load there.

## claude.ai copies

Chat, Cowork and desktop Local sessions still get these skills from claude.ai. After changing a skill here, upload its
folder as a ZIP on claude.ai so the copies don't drift. Synced skills only carry standard frontmatter (`name`,
`description`), so don't add Claude Code-only fields such as `when_to_use` or `paths` while claude.ai is a channel.

The terminal CLI lists each skill twice: once as a personal skill and once as `anthropic-skills:<name>`.
`syncClaudeAiSkills: false` in `~/.claude/settings.json` removes the second copy, but also every other account skill.

## Check

```bash
claude plugin validate --strict .
```
