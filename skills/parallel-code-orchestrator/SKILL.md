---
name: "parallel-code-orchestrator"
description: "Split a large coding task or a roadmap issue into independent pieces and run them on parallel subagents. Use for multi-file features, refactors, migrations, or when asked to orchestrate or parallelize."
---

# Parallel Code Orchestrator

You plan, delegate, integrate and verify; subagents implement. Without a subagent tool (Agent or Task), say so and work through the same plan sequentially.

Keep going without checking in, except for the cases in "When to stop and ask".

## Hard rules

**One repo per run.** Change only the repo this session started in: subagent worktrees cover no other repo, and work in another repo belongs to a fresh session there. Children in other repos are not units of this run. Read those repos freely, and report which of their children are ready.

**Model and effort on every spawn.** Pass both on every Agent call, except where the table says unset. An unset model runs on the session's model (general-purpose: on `CLAUDE_CODE_SUBAGENT_MODEL` if set); an unset effort follows the session's effort (`medium` by default on the 5.5 models). Per-call `effort` needs Claude Code v2.1.292+, and `CLAUDE_CODE_EFFORT_LEVEL`, when set, overrides it.

| Work | Model | Effort |
|---|---|---|
| Scouting, searching, read-only sweeps: the Explore agent | Haiku: pass `model: haiku` unless `~/.claude/agents/explore.md` exists and pins it | `medium`, never `low` (Haiku at `low` skips checks) |
| The repo's reviewer agent | Unset, so the pin in its file applies | Unset if its file pins one, else `high` |
| Issue-check runs | Sonnet | `high` |
| Mechanical units with a tight brief: renames, repeated edits, tests for existing code, docs | Sonnet | `medium` |
| Units needing design judgment, or defining a shared contract | Session model | `high` |
| Extremely complex coding or analysis the session model at `high` has already failed at, or clearly would: a novel algorithm, deep numeric or geometric work, a subtle multi-file bug hunt | Fable | `high`, never above |
| Planning, integration, conflicts | You, never delegated | |

If you can state exactly which files change and how, the unit is mechanical. A cheaper model needs a fuller brief with an example file to copy. When unsure, go one tier up, as far as the session model. A model or budget the user names overrides the table.

**Escalate effort before tier.** A unit too hard for its row: first the same model one effort level up (to `xhigh` at most), then one tier up (Sonnet to the session model), then Fable only for a unit that fits its row.

**Fable is the exception, not the tier above the session model.** Opus 5.5 scores higher than Fable 5.1 on Anthropic's published coding benchmarks (Terminal-Bench 4.0, FrontierCode, CursorBench; Anthropic says the real gap is narrower than the scores suggest), while Fable is slower, costs 2.5× Opus per token, and on Max may use at most 50% of the weekly limits (as of 2026-10-12, claude-kb ORCH-026, ORCH-027, ORCH-031; re-check when a model ships). So use it only for units that fit its row: never for reviewers, issue checks, scouting, docs or mechanical units, even when escalating. Fable units share the session's rate limit, so run at most two at a time. Set `model` on every spawn so nothing inherits Fable from the session. When the session itself runs on Fable, use Opus for the session-model rows; Explore then runs on Opus unless you pass `model: haiku`.

## When to stop and ask

- Anything irreversible or destructive: a deploy, a publish, a mutating cloud command. You do these yourself after an explicit go-ahead, never a subagent.
- Landing, where the repo says to ask (`main` or a PR).
- A roadmap child or plan that is stale: it no longer matches the code. Stop that unit, keep the rest of the wave going, and say what the issue should say instead.
- A request that conflicts with the roadmap or a repo's hard rules.
- For a large or hard-to-undo task: before launching, show the user the plan in a few lines and wait for a go-ahead.

Everything else: decide, note the decision in the progress file, and continue.

## 1. Load what already exists

These outrank this skill where they disagree.

**Roadmap issue.** If the task is a roadmap (a GitHub issue with ordered sub-issues, e.g. `osrs-tracker/osrs-tracker-web#159`) or an issue whose first line says `Part of roadmap owner/repo#N`, the decomposition is already done:

- `gh issue view` the roadmap: which repo skills to load, `## Order`, `### Checklist`, the shared context
- Children in order: `gh api --paginate 'repos/<owner>/<repo>/issues/<roadmap>/sub_issues?per_page=100'` (without the parameters the list stops at 30)
- What each child waits on: `gh api repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by --jq '[.[] | select(.state == "open") | .number]'` (the list includes closed issues, so filter), plus its first line (which also says what not to merge or deploy before which step)

Children are the work units; an open child that waits on nothing open is ready, and the ready children are the current wave. A child's `## Verify` is its done-when, and the file paths in its `## Problem` and `## Do` are the files it touches. A child without a `## Verify` has its check among the `## Do` steps; one whose first line names no limits takes them from the roadmap's Order. Split a large child further inside its repo, but never merge children into one unit. What the roadmap lists as considered and dropped stays dropped. Roadmaps go stale: check the evidence dates and the plan against the current code first.

Other sessions may be working the same roadmap. Skip children that are assigned or have an open PR (`gh pr list --search "<n>"`), and assign the ones you take when you launch: `gh api -X POST repos/<owner>/<repo>/issues/<n>/assignees -f 'assignees[]=<login>'` (`gh api user --jq .login` gives the login; `gh issue edit --add-assignee` can fail on a Projects (classic) error).

Where `gh issue` commands fail with a GraphQL error (cloud sessions), use REST: `gh api repos/<owner>/<repo>/issues/<n>` to read, the same path with `-X PATCH -F body=@file` to edit, and `gh api -X GET search/issues -f q='repo:<owner>/<repo> is:pull-request state:open <n>'` to look for an open PR.

Work that spans several sessions or repos and has no roadmap: suggest the `roadmap-issues` skill first.

**Repo rules.** Read `CLAUDE.md`, the repo's own skill, `.claude/agents/` (note a reviewer agent), and the hooks in `.claude/settings.json`.

## 2. Decide whether to orchestrate

A multi-agent run costs several times the tokens of doing it yourself. Orchestrate when at least three pieces can each be done without knowing how the others turned out. Otherwise do it directly: small tasks, chains where each step needs the last, pieces that share the same few files, and work whose design is still open.

For one repetitive change across 30 or more files, or "audit everything", use `/batch` or a dynamic workflow ("use a workflow") instead of waves of three to six: they scale to many agents and keep the results out of your context. Settle any shared contract yourself first.

## 3. Scout and baseline

Learn the layout, then list what parallel subagents would collide on. The repo's `CLAUDE.md` usually names these:

- **Shared files** every change wants: changelog, data-model or API docs, routes, registries, config, lockfiles, barrel exports
- **Shared code** every part builds on: common libraries, shared build config
- **Shared runtime**: dev-server ports, `.env` files, databases, anything with no staging copy
- **Worktree gaps**: whether a worktree has its dependencies installed, an `.env`, and a path to sibling repos (a `.worktreeinclude` file copies gitignored files such as `.env` into new worktrees)

Search a large area with Explore, as the table's first row sets it. Run the repo's verify command now and record what already fails.

## 4. Plan the units

Per unit: **goal** (for a roadmap child, the issue reference), **owned files**, **read-only context**, **done-when**, **model and effort** (from the table).

- **No two units own the same file.** Shared files, the changelog above all, are yours during integration; units report what they need added. Compare the files roadmap children touch before putting two in one wave.
- **Shared code goes to one unit**, never two, and in an earlier wave than the units that build on it.
- **Shared runtime stays with you.** Subagents don't start dev servers or write to a shared database; you run such checks once on the integrated result.
- **Decide once, share everywhere.** Subagents can't see each other's choices, and mismatched choices are the usual integration failure. Settle whatever two units would each decide for themselves (signatures, types, endpoint shapes, schemas, naming, error handling, which pattern or library, user-facing wording) and paste identical text into every brief that needs it. A unit that still has open design decisions isn't ready to run in parallel.
- **A feature and its tests are one unit.** Splitting the tests for new code into another unit costs more coordination than it saves. A unit that only adds tests for existing code is fine.
- **Done-when is a command.** If no test or check can show a unit is done, write that check first or keep the unit yourself.
- **Risky units plan first.** Have the subagent return its plan, then message it to proceed (`SendMessage` to its id or name).
- **Upstream first.** A unit that needs a change in another repo waits until that repo's session has landed it. A unit that needs an unpublished package or an undeployed service cannot be verified against it: test against a local build and mark it not verified, or stop and ask for the publish go-ahead.
- **Waves by dependency**, three to six units each. A unit you could do in two tool calls is not worth a subagent.

**Context budget.** Give every unit a budget in its brief: about 200k tokens for reviewers, checks and mechanical units, about 300k for implementation units. A unit near its budget stops at a clean point, commits, writes its handoff file ([references/handoff-and-progress.md](references/handoff-and-progress.md) has the format) and reports `STATUS: HANDOFF`. A unit that won't fit in one budget is too big: split it, or plan it as a chain of subagents passing a handoff file. Subagents compact automatically, but a compacted summary loses decisions and dead ends that a handoff file keeps.

**Progress file.** Write the plan to a file outside the repo's tracked files: units, owned files, models and effort, waves, branch names, status, decisions. Update it as units finish and re-read it after any context compaction. A session that resumes a stopped run reads it and `git worktree list` first. Read [references/handoff-and-progress.md](references/handoff-and-progress.md) before writing it, and again before a compaction or a session change.

## 5. Brief each subagent

A subagent gets `CLAUDE.md` and your brief, and nothing else you can rely on: not the conversation, not the repo skill, not the other units. Its `CLAUDE.md` comes from the main checkout, not its worktree's branch, so when an earlier wave changed `CLAUDE.md` or `.claude/rules/`, the brief must say what changed.

Read [references/brief-template.md](references/brief-template.md) before writing the first brief, and fill in every section.

## 6. Launch

Send the whole wave in one message so it runs concurrently. Give each code-writing unit its own worktree by passing `isolation: "worktree"` on the Agent call itself, not only in an agent's frontmatter: with agent teams enabled, a named spawn without it becomes a teammate working in the main checkout.

A subagent's worktree starts from the repo's default branch, not from your branch. From wave 2 on, either the previous wave has landed, or the brief starts by merging your integration branch. Setting `worktree.baseRef` to `"head"` in settings does the same by starting worktrees from your current branch.

## 7. Triage, integrate, verify

Read [references/triage.md](references/triage.md) when the first report arrives: what to do per status, the size check before every resume, and rate limits.

A report is a claim. For each unit, read the diff (cheaper models' first), check it stayed in its owned files and followed the shared decisions, and collect its shared-file entries. Compare the decisions the units reported and settle any that conflict before merging.

Then keep roadmap children as separate branches (one PR per child) and merge them into a throwaway integration branch to test together; other work lands as one integration branch. Add the shared-file edits (one changelog heading for the day), wire the seams, and run the full verify command on the combined result. Subagents never pushed, so any pre-push check runs on your push. If something fails, find which seam broke before changing code.

Last, check the result against the original goal, not only the units: exercise the change end to end the way the request or roadmap describes it.

## 8. Review

Run these in parallel on the integrated result, then fix and rerun until clean.

**The reviews the repo prescribes**, as its skill or `CLAUDE.md` describes them: its reviewer agent (`.claude/agents/`, e.g. `conventions-reviewer`), and any other review it names, such as `/code-review` run in a subagent. Check another review's findings against the code before fixing them, as for the reviewer agent below. For the reviewer agent:

- Spawn it by `subagent_type` without `model`: a model passed at spawn overrides the one its file pins.
- Name the branch or paths; its default diff assumes it runs in the checkout under review.
- If it is not available as an agent type, spawn a general subagent told to follow that file exactly, read-only, on the model the file pins.
- Check each **breaks** and **violates** finding against the code before fixing it; drop the ones that don't hold and say so in the report. Fix the rest. Pass **check** findings to the user as written.
- Run it on the whole integrated diff, not per unit: its rules span files.

**An issue check**, for roadmap children: one fresh subagent per child (Sonnet, `high`) compares that child's diff with the issue text and reports what is missing, extra or different. You wrote the brief, so you are a poor judge of whether it matched the issue.

None of these replaces your own diff reading or the verify command.

## 9. Land and report

Landing follows the repo's rules. Honour every "do not merge or deploy before" note on a roadmap child, even when its code is ready. After a child lands, tick its box in the roadmap checklist (re-read the body right before editing; other sessions edit it too) and add a dated update line if what you learned makes the shared context wrong for the open children. Unassign any child you claimed and did not finish. Remove the integration branch and the worktrees of finished units; a worktree that holds changes is not cleaned up for you.

If the run changed something the repo's docs describe (layout, commands, env vars, ports, a documented contract), run the `refresh-md-files` skill on a Sonnet subagent at `medium`, scoped to the affected `.md` files, and put its findings in the report. Fixing the docs is a separate, doc-only change.

Report, outcome first:

- What changed; for a roadmap, which children are done and which are now ready
- Verify commands run on the integrated result, and their status
- Review result: clean, the open **check** findings, and the findings dropped as not holding
- Anything unfinished, skipped or assumed

Leave out which subagent or model did what unless asked.
