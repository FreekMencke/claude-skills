# Triage and resuming subagents

## By status

- **DONE**: review it.
- **DONE_WITH_CONCERNS**: settle correctness and scope concerns before review.
- **NEEDS_CONTEXT**: send the missing context to the same subagent.
- **BLOCKED**: find the cause. Missing context: supply it. Too hard for the model: escalate as the hard rules say (effort first, then one tier up, Fable only for a unit that fits its row). Too big: split it. Issue or plan wrong: see "When to stop and ask".
- **HANDOFF**: spawn a fresh subagent, same tier or lower, whose brief is "continue from <HANDOFF.md>" plus the original brief's Scope, Decisions, Verify and Limits.

Several units BLOCKED on the same thing: fix it once yourself, then resume them.

## Fix rounds

For fixes, message the same subagent so it keeps its context, after the size check below. After two failed rounds, escalate (same model one effort level up, then a fresh subagent one tier up, Fable only for a unit that fits its row) or do it yourself. Never resend an unchanged brief.

## Size check before every resume

The size is the total tokens in its last completion notification. `SendMessage` continues its whole context, and the new work adds to it. Resume only when its size plus the new work stays inside its budget: a small fix needs about 50k of room, anything larger about 100k. Without that room, give it no new work: send one message asking it to commit and write its handoff file, then spawn a fresh subagent from that file. This applies to every older subagent you restart, including ones stopped by a rate limit.

A subagent's prompt cache lasts 5 minutes. A resume after it sat idle for longer re-reads its whole context uncached, so for a large subagent idle that long, prefer a fresh subagent from its handoff file.

Every resume message states the subagent's current size and its budget, and repeats the budget rule from `## Limits`. That covers subagents whose brief had no budget, and lets one that crosses its budget during the resumed work stop there with a handoff instead of carrying on.

## Rate limits

A subagent that stops on a usage or rate limit is reported as failed, but its work isn't wrong: resume it once the limit resets, after the size check. When several heavy units hit the limit, run fewer at once instead of resuming them all together.

## Optional: enforce DONE with a hook

A repo with a fast verify command can add a `SubagentStop` hook in its own `.claude/settings.json` that blocks a worker from stopping until the check passes. That is per-repo config, not part of this skill; use it where a repo already has one.
