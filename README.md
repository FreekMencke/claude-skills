# claude-skills

Source of truth for my personal Claude Code skills. The repo is laid out as a skills-dir plugin (`freek-skills`;
plugin names can't start with `claude-`) and a marketplace, so `claude plugin validate .` and `claude plugin eval .` work on it.

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
folder as a ZIP on claude.ai so the copies don't drift. Synced skills only carry standard frontmatter (`name`,
`description`), so don't add Claude Code-only fields such as `when_to_use` or `paths` while claude.ai is a channel.

The terminal CLI lists each skill twice: once as a personal skill and once as `anthropic-skills:<name>`.
`syncClaudeAiSkills: false` in `~/.claude/settings.json` removes the second copy, but also every other account skill.

## Check

```bash
claude plugin validate .
```

Not `--strict`: it fails on the missing `version`, which is left out on purpose so installs track commits.
