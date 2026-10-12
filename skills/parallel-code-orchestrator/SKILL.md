---
name: "parallel-code-orchestrator"
description: "Split a large coding task or a roadmap issue into independent pieces, run them on parallel subagents, then integrate, verify and run the repo's reviewer agent. Use for multi-file features, refactors, migrations, or when asked to orchestrate or parallelize."
---

# Parallel Code Orchestrator

You plan, delegate, integrate and verify; subagents implement. Without a subagent tool (Agent or Task), say so and work through the same plan sequentially.

Keep going without checking in, except for the cases in "When to stop and ask".

## 1. Load what already exists

These outrank this skill where they disagree.

**Roadmap issue.** If the task is a roadmap (a GitHub issue with ordered sub-issues, e.g. `osrs-tracker/osrs-tracker-web#159`) or an issue whose first line says `Part of roadmap owner/repo#N`, the decomposition is already done:

- `gh issue view` the roadmap: which repo skills to load, `## Order`, `### Checklist`, the shared context
- Children in order: `gh api repos/<owner>/<repo>/issues/<roadmap>/sub_issues`
- What each child waits on: `gh api repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by --jq '[.[] | select(.state == "open") | .number]'` (the list includes closed issues, so filter), plus its first line (which also says what not to merge or deploy before which step)

Children are the work units; an open child that waits on nothing open is ready, and the ready children are the current wave. A child's `## Verify` is its done-when, and the file paths in its `## Problem` and `## Do` are the files it touches. A child without a `## Verify` has its check among the `## Do` steps; one whose first line names no limits takes them from the roadmap's Order. Split a large child further inside its repo, but never merge children into one unit. What the roadmap lists as considered and dropped stays dropped. Roadmaps go stale: check the evidence dates and the plan against the current code first.

Other sessions may be working the same roadmap. Skip children that are assigned or have an open PR (`gh pr list --search "<n>"`), and assign the ones you take when you launch: `gh issue edit <n> --add-assignee @me`.

Where `gh issue` commands fail with a GraphQL error (cloud sessions), use REST: `gh api repos/<owner>/<repo>/issues/<n>` to read, the same path with `-X PATCH -F body=@file` to edit, `-X POST .../issues/<n>/assignees -f 'assignees[]=<login>'` to assign (`gh api user --jq .login` gives the login), and `gh api -X GET search/issues -f q='repo:<owner>/<repo> is:pull-request state:open <n>'` to look for an open PR.

Work that spans several sessions or repos and has no roadmap: suggest the `roadmap-issues` skill first.

**One repo per run.** Change only the repo this session started in: subagent worktrees cover no other repo, and work in another repo belongs to a fresh session there. Children in other repos are not units of this run. Read those repos freely, and report which of their children are ready.

**Repo rules.** Read `CLAUDE.md`, the repo's own skill, `.claude/agents/` (note a reviewer agent), and the hooks in `.claude/settings.json`.

## 2. Decide whether to orchestrate

A multi-agent run costs several times the tokens of doing it yourself. Orchestrate when at least three pieces can each be done without knowing how the others turned out. Otherwise do it directly: small tasks, chains where each step needs the last, pieces that share the same few files, and work whose design is still open.

## 3. Scout and baseline

Learn the layout, then list what parallel subagents would collide on. The repo's `CLAUDE.md` usually names these:

- **Shared files** every change wants: changelog, data-model or API docs, routes, registries, config, lockfiles, barrel exports
- **Shared code** every part builds on: common libraries, shared build config
- **Shared runtime**: dev-server ports, `.env` files, databases, anything with no staging copy
- **Worktree gaps**: whether a worktree has its dependencies installed, an `.env`, and a path to sibling repos (a `.worktreeinclude` file copies gitignored files such as `.env` into new worktrees)

Use Haiku subagents to search a large area. Run the repo's verify command now and record what already fails.

## 4. Plan the units

Per unit: **goal** (for a roadmap child, the issue reference), **owned files**, **read-only context**, **done-when**, **model**.

- **No two units own the same file.** Shared files, the changelog above all, are yours during integration; units report what they need added. Compare the files roadmap children touch before putting two in one wave.
- **Shared code goes to one unit**, never two, and in an earlier wave than the units that build on it.
- **Shared runtime stays with you.** Subagents don't start dev servers or write to a shared database; you run such checks once on the integrated result.
- **Decide once, share everywhere.** Subagents can't see each other's choices, and mismatched choices are the usual integration failure. Settle whatever two units would each decide for themselves (signatures, types, endpoint shapes, schemas, naming, error handling, which pattern or library, user-facing wording) and paste identical text into every brief that needs it. A unit that still has open design decisions isn't ready to run in parallel.
- **Done-when is a command.** If no test or check can show a unit is done, write that check first or keep the unit yourself.
- **Risky units plan first.** Have the subagent return its plan, then message it to proceed (`SendMessage` to its id or name).
- **Upstream first.** A unit that needs a change in another repo waits until that repo's session has landed it. A unit that needs an unpublished package or an undeployed service cannot be verified against it: test against a local build and mark it not verified, or stop and ask for the publish go-ahead.
- **Waves by dependency**, three to six units each. A unit you could do in two tool calls is not worth a subagent.

**Model per unit.** Set it on every spawn except a repo agent that pins its own model: a model set at spawn overrides the pin. Anything else left unset runs on the session's model.

| Work | Model |
|---|---|
| Scouting, searching, read-only sweeps | Haiku |
| The repo's reviewer agent | Unset, so the pin in its file applies |
| Issue-check runs | Sonnet |
| Mechanical units with a tight brief: renames, repeated edits, tests for existing code, docs | Sonnet |
| Units needing design judgment, or defining a shared contract | Session model |
| Extremely complex coding or analysis the session model has already failed at, or clearly would: a novel algorithm, deep numeric or geometric work, a subtle multi-file bug hunt | Fable |
| Planning, integration, conflicts | You, never delegated |

If you can state exactly which files change and how, the unit is mechanical. A cheaper model needs a fuller brief with an example file to copy. When unsure, go one tier up, as far as the session model. A model or budget the user names overrides the table.

**Fable is the exception, not the tier above the session model.** Use it only for units that fit its row: never for reviewers, issue checks, scouting, docs or mechanical units, even when escalating. Fable units share the session's rate limit, so run at most two at a time. Set `model` on every spawn so nothing inherits Fable from the session; when the session itself runs on Fable, use Opus for the session-model rows.

**Context budget.** Give every unit a budget in its brief: about 200k tokens for reviewers, checks and mechanical units, about 300k for implementation units. A unit near its budget stops at a clean point, commits, writes its handoff file and reports `STATUS: HANDOFF`. A unit that won't fit in one budget is too big: split it, or plan it as a chain of subagents passing a handoff file. Subagents compact automatically, but a compacted summary loses decisions and dead ends that a handoff file keeps.

**Handoff file.** Lets a fresh subagent or session continue without the old one's context. It lives in the unit's worktree or your scratch directory, untracked unless the repo wants it, and holds:

- **Goal and done-when**, copied from the brief, plus anything added since
- **State**: worktree path, branch, last commit, and the last commit known to be good when later ones regress
- **Approach**: what works and why; what was tried and dropped and why, so it isn't retried
- **Commands and scripts**, in run order, with paths
- **Data formats**, each with one concrete example
- **Remaining work**, each item with its done-when
- **Pitfalls** found along the way

**Progress file.** Write the plan to a file outside the repo's tracked files: units, owned files, models, waves, branch names, status, decisions. Update it as units finish and re-read it after any context compaction. A session that resumes a stopped run reads it and `git worktree list` first. Before a compaction or a session change, bring it up to handoff-file standard, including the worktree and branch of every subagent still running.

Background subagents report only to the session that spawned them. While one runs, compact this session rather than starting a new one; a new session would have to find its result by hand from the progress file.

**Rate limits.** A subagent that stops on a usage or rate limit is reported as failed, but its work isn't wrong: resume it once the limit resets, after the size check in step 7. When several heavy units hit the limit, run fewer at once instead of resuming them all together.

For a large or hard-to-undo task, show the user the plan in a few lines and wait for a go-ahead before launching.

## 5. Brief each subagent

A subagent gets `CLAUDE.md` and your brief, and nothing else you can rely on: not the conversation, not the repo skill, not the other units.

```
## Task
<one-paragraph goal>
<roadmap child: "Implement owner/repo#N. Read it and the roadmap
owner/repo#M (gh issue view, or gh api repos/<owner>/<repo>/issues/<n>).">
<wave 2 onwards: "First merge branch <integration branch> into yours.">

## Rules
Load the repo's skill (<name>) before writing anything.
<worktree gaps from step 3: where to install dependencies, the absolute
path to sibling repos>

## Scope
You may edit: <owned files>
Read but do not edit: <paths>
Nothing else, including <the shared files from step 3>. Needed changes
outside your scope: report them, don't make them.

## Decisions already made
<the shared decisions from step 4, word for word>
<what the roadmap defers or dropped>

## Verify
Run: <the done-when command, then the verify command or subset>.
Fix failures you caused. Already failing, ignore: <list>

## Limits
Commit on your worktree branch with normal signing. No push, deploy,
publish, dev server, issue edits, or anything that changes remote state.
Context budget: about <N>k tokens. When you get close, stop at a clean
point: commit, write <path>/HANDOFF.md (goal and done-when, state,
approach and what was dropped, commands, data formats, remaining work,
pitfalls) and report STATUS: HANDOFF.

## Report, under 20 lines; the diff is the detail
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED | HANDOFF
- Branch, and files changed with one line each
- Verify commands and results
- The entry each shared file needs (changelog line, doc row)
- Decisions you made that another unit might also have faced
- Concerns, out-of-scope changes needed, or what blocks you
```

## 6. Launch

Send the whole wave in one message so it runs concurrently. Give each code-writing unit its own worktree.

A subagent's worktree starts from the repo's default branch, not from your branch. From wave 2 on, either the previous wave has landed, or the brief starts by merging your integration branch. Setting `worktree.baseRef` to `"head"` in settings does the same by starting worktrees from your current branch.

## 7. Triage, integrate, verify

By status:

- **DONE**: review it.
- **DONE_WITH_CONCERNS**: settle correctness and scope concerns before review.
- **NEEDS_CONTEXT**: send the missing context to the same subagent.
- **BLOCKED**: find the cause. Missing context: supply it. Too hard for the model: one tier up (Fable only for a unit that fits its row). Too big: split it. Issue or plan wrong: see "When to stop and ask".
- **HANDOFF**: spawn a fresh subagent, same tier or lower, whose brief is "continue from <HANDOFF.md>" plus the original brief's Scope, Decisions, Verify and Limits.

Several units BLOCKED on the same thing: fix it once yourself, then resume them.

**Before every resume, check the subagent's size**: the total tokens in its last completion notification. `SendMessage` continues its whole context, and the new work adds to it. Resume only when its size plus the new work stays inside its budget: a small fix needs about 50k of room, anything larger about 100k. Without that room, give it no new work: send one message asking it to commit and write its handoff file, then spawn a fresh subagent from that file. This applies to every older subagent you restart, including ones stopped by a rate limit.

Every resume message states the subagent's current size and its budget, and repeats the budget rule from `## Limits`. That covers subagents whose brief had no budget, and lets one that crosses its budget during the resumed work stop there with a handoff instead of carrying on.

For fixes, message the same subagent so it keeps its context, after the size check. After two failed rounds, use a fresh subagent one tier up (Fable only for a unit that fits its row) or do it yourself. Never resend an unchanged brief.

A report is a claim. For each unit, read the diff (cheaper models' first), check it stayed in its owned files and followed the shared decisions, and collect its shared-file entries. Compare the decisions the units reported and settle any that conflict before merging.

Then keep roadmap children as separate branches (one PR per child) and merge them into a throwaway integration branch to test together; other work lands as one integration branch. Add the shared-file edits (one changelog heading for the day), wire the seams, and run the full verify command on the combined result. Subagents never pushed, so any pre-push check runs on your push. If something fails, find which seam broke before changing code.

Last, check the result against the original goal, not only the units: exercise the change end to end the way the request or roadmap describes it.

## 8. Review

Run these in parallel on the integrated result, then fix and rerun until clean.

**The repo's reviewer agent** (`.claude/agents/`, e.g. `conventions-reviewer`):

- Name the branch or paths; its default diff assumes it runs in the checkout under review.
- If it is not available as an agent type, spawn a general subagent told to follow that file exactly, read-only, on the model the file pins.
- Fix every **breaks** and **violates** finding. Pass **check** findings to the user as written.
- Run it on the whole integrated diff, not per unit: its rules span files.

**An issue check**, for roadmap children: one fresh Sonnet subagent per child compares that child's diff with the issue text and reports what is missing, extra or different. You wrote the brief, so you are a poor judge of whether it matched the issue.

Neither replaces your own diff reading or the verify command.

## 9. Land and report

Landing follows the repo's rules. Honour every "do not merge or deploy before" note on a roadmap child, even when its code is ready. After a child lands, tick its box in the roadmap checklist (re-read the body right before editing; other sessions edit it too) and add a dated update line if what you learned makes the shared context wrong for the open children. Unassign any child you claimed and did not finish. Remove the integration branch and the worktrees of finished units; a worktree that holds changes is not cleaned up for you.

If the run changed something the repo's docs describe (layout, commands, env vars, ports, a documented contract), run the `refresh-md-files` skill on a Sonnet subagent, scoped to the affected `.md` files, and put its findings in the report. Fixing the docs is a separate, doc-only change.

Report, outcome first:

- What changed; for a roadmap, which children are done and which are now ready
- Verify commands run on the integrated result, and their status
- Review result: clean, or the open **check** findings
- Anything unfinished, skipped or assumed

Leave out which subagent or model did what unless asked.

## When to stop and ask

- Anything irreversible or destructive: a deploy, a publish, a mutating cloud command. You do these yourself after an explicit go-ahead, never a subagent.
- Landing, where the repo says to ask (`main` or a PR).
- A roadmap child or plan that is stale: it no longer matches the code. Stop that unit, keep the rest of the wave going, and say what the issue should say instead.
- A request that conflicts with the roadmap or a repo's hard rules.

Everything else: decide, note the decision in the progress file, and continue.