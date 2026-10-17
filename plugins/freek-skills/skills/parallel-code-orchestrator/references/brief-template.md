# Brief template

Fill in every section for each subagent. Keep the sections every unit shares (Rules, Decisions, Limits) word for word the same and before the per-unit details where you can: identical prefixes are cheaper to cache.

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
<when an earlier wave changed CLAUDE.md or .claude/rules/: "Your CLAUDE.md
is loaded from the main checkout and is out of date: <what changed>.">

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
A syntax-only check, or a check command that failed to start, does not
count: it doesn't exercise the change. If no real check can run here,
report which one and why instead of reporting DONE.
Fix failures you caused. Already failing, ignore: <list>

## Limits
Commit on your worktree branch with normal signing. No push, deploy,
publish, dev server, issue edits, or anything that changes remote state.
Don't spawn subagents except read-only Explore searches.
Context budget: about <N>k tokens. When you get close, stop at a clean
point: commit, write <scratchpad>/<unit>/HANDOFF.md, outside your
worktree (goal and done-when, state,
approach and what was dropped, commands, data formats, remaining work,
pitfalls) and report STATUS: HANDOFF.

## Report, under 20 lines; the diff is the detail
Every claim rests on a command result from this session; name any check
you didn't run. BLOCKED is a valid report: say what blocked you and stop
instead of working around it, such as skipping a check or editing outside
your scope.
STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED | HANDOFF
- Branch, and files changed with one line each
- Verify commands and results
- The entry each shared file needs (changelog line, doc row)
- Decisions you made that another unit might also have faced
- Concerns, out-of-scope changes needed, or what blocks you
```

For a HANDOFF continuation, the brief is "Continue from <scratchpad>/<unit>/HANDOFF.md" plus the original brief's Scope, Decisions, Verify and Limits.
