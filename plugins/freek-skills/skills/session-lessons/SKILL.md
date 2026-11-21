---
name: session-lessons
description: "Turns a session's lessons (user corrections, repeated rounds, failed attempts, tool surprises) into lasting changes without duplicates: a tightened line in the repo's skills, agents or docs, a hook that enforces it, a proposed global rule, or an issue in another repo. Use at the end of a session, for a retro, or to process learnings into docs and skills. Not for a handoff (handoff) or a docs audit (refresh-md-files)."
---

# Session lessons

What a session taught lives only in its conversation. This skill turns each lesson into the cheapest change that will
hold, in the place a later session reads at the moment it matters, without duplicating or contradicting a rule that is
already there.

Collecting needs the conversation, so steps 1 and 2 run in the session itself. A fresh session or subagent can't see
it; see "Long sessions" for handing steps 3 to 5 to one.

Not for:

- Product decisions: they go in the design docs when they're made.
- Loosening or dropping a rule because this session found it inconvenient: report the friction as a lesson instead.
- What the code or git history already records: the fix itself, a file layout, who changed what.
- Passing the session's state to the next one (`handoff`), auditing docs against the code (`refresh-md-files`),
  writing a new skill (`skill-workshop`).

## 1. Collect

Go through the whole conversation, including any compaction summary at its start. A lesson is one of:

- A correction from the user, or a choice they made about how to work.
- Something that took more than one round, and what the first brief or approach lacked.
- An attempt that failed, and its cause once found.
- A tool, command or service that behaved differently from what was expected or documented.
- A rule that was missing, or one that was followed but cost time.

Keep a lesson only when it would change what a fresh session does next time. Drop one-offs, typos and what the model
would do anyway. Merge lessons that say the same thing.

Write one numbered line each:

```
N. <the rule, as an instruction> | <the incident: what happened, with its PR, issue or commit, and the date> | "<the user's words, if any>" | guess: <target>
```

Look up a reference the conversation only implies (`gh`, `git log`) rather than recall it. A cause the session never
verified is marked "likely", with what would confirm it.

## 2. Sort

For each lesson, choose the cheapest form that will hold, in this order:

1. **Enforced**: a hook, script, lint rule or CI check that makes the mistake impossible or loud. Prefer it when the
   rule is mechanical (a command never to run, a step always to run, a file never to edit by hand). Delete the written
   rule it replaces in the same change.
2. **A line where it's read when it matters**: in the skill that runs that step, the agent that does that work, or the
   doc for that area, not in whichever file is nearest.
3. **A domain note**: a fact about the project's stack (this API returns X, that tool needs Y), in the repo's notes for
   that area if it keeps them, otherwise in the doc for that area.
4. **A new skill or agent**: only when the same instructions have been written out in several briefs or sessions.
   Propose it; writing it is a task of its own.

And by where it holds:

- **This repo**: one of the forms above.
- **Every repo of this user**: a line for their global instructions (such as `~/.claude/CLAUDE.md`), proposed, never
  written.
- **This repo on this machine only** (a local path, a machine quirk): `CLAUDE.local.md` or auto memory. Both stay on
  this machine, and subagents don't load auto memory, so nothing CI, a teammate or a subagent needs goes there.
- **Another repo** (a fault in a shared tool, a knowledge base, a third-party skill): an issue there with the proof, in
  the follow-up format of the `roadmap-issues` skill.
- **Nowhere**: a one-off, already enforced, or already recorded. Say which.

## 3. Check what's already there

For each lesson with a target in the repo, search the instruction files and docs for an existing rule:
`rg -n -i --hidden -g '!.git'` with two or three of its key words from the repo root (without `--hidden` it skips
`.claude/`, `.agents/` and `.github/`), so it covers `CLAUDE.md`, `AGENTS.md`, the skills, the agents and the docs.
Read each hit, then:

- **Already recorded**: skip it, and give the `path:line`.
- **Covered, but loose or in the wrong place**: tighten or move that line.
- **Contradicted**: don't add the opposite. Put both to the user in the plan.
- **Missing**: add one line where it's read when it matters.

Prefer changing a line to adding one. Keep each file's voice, format and length, and follow the repo's rules for that
kind of file (a skill's description and length, a docs style guide). Keep the incident beside the rule in a few words,
such as `(#123, 2026-11-20)`: a rule without its reason gets loosened by the next session that finds it inconvenient.

## 4. Plan, then wait for the go-ahead

Change nothing before the user has seen this:

```markdown
## Session lessons: plan

| # | Lesson | Target | Already there | Action |
|---|---|---|---|---|
| 1 | <rule> | `<path>` (<section>) | `<path:line>` or none | add / tighten / move / enforce / skip: <why> |

**Proposed for your global instructions** (not applied)
- `<line>`, under <heading>: lesson N

**Issues to open elsewhere**
- <owner/repo>: <title>: lesson N

**Not recorded**
- N: one-off / enforced by <tool> / already at `<path:line>` / a product decision
```

Drop sections that would be empty. If no lesson qualifies, say "No lessons to record", list what was considered, and
stop. The user may cut, reword or move lessons; follow their version. An edit to a `CLAUDE.md` or `AGENTS.md` is
listed as its own row, so the go-ahead names it.

Without a shell or the repo (claude.ai chat, say), stop at the plan: give each line's full proposed text, write "not
checked" under **Already there**, and leave the edits to the user.

## 5. Write

After the go-ahead, and only what it covers:

- Branch, commit and open the PR by the repo's own rules: its branch names, changelog, verify command and review
  process. Docs and skill lines go in one PR; a hook, script or CI change goes in the same PR when the repo allows it.
- Open the issues elsewhere, one per repo, and link them from the PR.
- PR description: one bullet per file with the lessons it took, the verify command you ran and its result.

## 6. Report

```markdown
## Session lessons: done

PR: <link>. Verify: `<command>`: <result>.

| # | Lesson | Outcome |
|---|---|---|
| 1 | <rule> | added at `<path:line>` / tightened `<path:line>` / enforced by `<file>` / already recorded at `<path:line>` / not recorded: <reason> |

**Proposed global lines** (not applied)
- `<line>`

**Issues opened**
- <link>
```

## Long sessions: hand steps 3 to 5 to a subagent

When the context is nearly full, do steps 1 and 2, write the numbered list to a file in the session's scratchpad (or
`/tmp`; not the repo), and spawn a fresh subagent with the brief below. It sees none of the conversation, so the file
carries everything: the rule, the incident, the user's words and the target guess. Show its plan to the user, then,
after the go-ahead, continue the same subagent or start a new one with the approved plan.

```
Lessons from a session are in <file>, one per line: rule | incident | the user's words | target guess. You can't see
that session; the file is all there is. The repo is <path>.

1. Read the repo's instructions (CLAUDE.md, AGENTS.md, contributing docs) and its rules for skills and docs.
2. For each lesson, search the instruction files, skills, agents and docs with `rg -n -i --hidden -g '!.git'` on its
   key words from the repo root, and read the hits.
3. Decide per lesson: already recorded (give path:line), tighten or move an existing line, add one line where it's
   read when it matters, enforce with a hook or check, or skip with the reason. Never add a duplicate or loosen a
   rule; prefer changing a line to adding one; keep each file's voice and length; keep the incident beside the rule.
4. Change nothing. Return the plan as a table: # | lesson | target | already there | action. List separately the
   lines for the user's global instructions and the issues for other repos.
```

The writing brief, after the go-ahead: "Apply this approved plan in <path>, by the repo's own rules for branches, PRs
and verifying: <plan>. Change nothing it doesn't list. Return the PR link, the verify result and the outcome per
lesson."
