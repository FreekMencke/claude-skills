# Handoff file and progress file

## Handoff file

Lets a fresh subagent or session continue without the old one's context. It lives in your session's scratchpad, one folder per unit (`<scratchpad>/<unit>/HANDOFF.md`), or, in a session without a scratchpad, a git-ignored folder in the main checkout. Never in the unit's worktree: removing a worktree has lost untracked and gitignored files. It holds:

- **Goal and done-when**, copied from the brief, plus anything added since
- **State**: worktree path, branch, last commit, and the last commit known to be good when later ones regress
- **Approach**: what works and why; what was tried and dropped and why, so it isn't retried
- **Commands and scripts**, in run order, with paths
- **Data formats**, each with one concrete example
- **Remaining work**, each item with its done-when
- **Pitfalls** found along the way

## Progress file

The orchestrator's own plan and state, in a file outside the repo's tracked files:

- Units: goal, owned files, model and effort, wave, branch and worktree, status
- Decisions: the shared decisions pasted into briefs, and every decision taken instead of asking

Update it as units finish, and re-read it after any context compaction. A session that resumes a stopped run reads it and `git worktree list` first.

Before a compaction or a session change, bring it up to handoff-file standard, including the worktree and branch of every subagent still running.

Background subagents report only to the session that spawned them. While one runs, compact this session rather than starting a new one; a new session would have to find its result by hand from the progress file.
