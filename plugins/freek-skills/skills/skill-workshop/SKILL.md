---
name: "skill-workshop"
description: "Write a new skill, or audit and improve an existing one, grounded in real material and online research: official docs, similar published skills and existing solutions. Use when asked to create, draft, review, audit, research, compare, tighten, align or fix a skill or a SKILL.md. For measured trigger or benchmark runs, use claude plugin eval or skill-creator instead."
---

# Skill workshop

A skill is read by a fresh session with no context, which follows it literally. Write and audit for that reader.

This skill works by reading, researching online, checking and comparing. For measured runs, use `claude plugin eval` (trigger cases and with-and-without comparisons for a plugin or skills folder) or `skill-creator` (benchmarks, description tuning). `/skill-doctor` shows each loaded skill's context cost and how often it is invoked, not whether it triggers correctly.

To review an existing skill, go to "Auditing a skill".

## Writing a skill

### 1. Scope

Ask only what changes the build: what the skill does, when it should load, what it outputs. At most three questions, as choices. For everything else pick a default and say which.

### 2. Ground it in real material

Read what the skill will work on before drafting:

- The repo's agent instructions (`CLAUDE.md`, `AGENTS.md`), its skills, its agents and its hooks
- Two real examples of the output the skill should produce (an issue, a report, a PR), as raw text. A summarising reader changes headings and wording.
- The user's own rules on the subject, wherever they keep them. Ask them to paste what you cannot read.

Use the user's rules in their own words. Keep a list of everything you add yourself.

### 3. Draft

- **Self-contained.** No pointer to memory, to a conversation, or to an example the reader may be unable to open. Examples are optional references, never the specification.
- **Templates where shape matters.** Give the output's skeleton, and say what to output when there is nothing to report.
- **Generic rules, local facts.** State the rule once and let each repo's own docs supply the specifics. Rules copied from a repo go stale.
- **A go-ahead before anything public or irreversible.** A skill that audits reports first and edits only after a go-ahead.
- **Commands that work where it runs.** A terminal and a cloud session allow different things; give the fallback.
- **Boundaries.** Say what the skill does not do and which skill does.
- **Plain rules.** One rule per line, with a clause of why when the reason is not obvious. No capitals for emphasis.

### 4. Research online

Search the web for this; what you remember about a tool or platform goes stale. Look for three kinds of source:

- **Official documentation** for everything the skill touches: the agent platform's own pages on skills and subagents, and the API or CLI the skill calls.
- **Similar skills.** Find two to five published skills that do the same job, in skill registries and in the popular skill collections on GitHub. Read the actual `SKILL.md`, not the listing's summary of it. Mark any source you could only read as a summary.
- **Existing solutions.** How others solved the underlying problem: engineering write-ups, the tools built for it, and the arguments against the approach.

Adopt an idea only when it closes a gap you can name in this skill, and note what you left out and why. Give the user a comparison table and a list of sources with links. Without web access, say so and mark the skill as not compared.

### 5. Check every claim

Check every command, API call, path, flag and platform behaviour in the draft against the official documentation from step 4, or by running it read-only. A skill that states something false is followed anyway. Keep a list of what you could not check.

### 6. Name and description

The description decides whether the skill loads. State what it does and when to use it, in the third person, using the words the user would type and every verb the skill supports. The name says what the skill does; when the behaviour changes, check the name still fits.

- **Length.** 1,024 characters is the hard limit for upload to claude.ai and the API. Claude Code truncates a listing entry at 1,536 and drops whole descriptions when the listing is over budget, and every character is paid on every turn. Aim for about 400.
- **Use case first.** Truncation cuts the end, so the main use case goes in the first sentence.
- **Outcome, not steps.** Never summarise the workflow's steps or their order; a session may follow the summary and skip the body.
- **Boundaries.** When a sibling skill shares vocabulary, end with a one-line "Not for X: use Y" that names it.
- **Frontmatter.** A skill that also goes to claude.ai keeps to `name` and `description`: a standalone ZIP upload rejects Claude Code-only fields, a plugin upload accepted them in one test (2026-10-15), and whether a marketplace sync accepts them is untested. Claude Code-only fields such as `when_to_use` or `paths` are for skills that live only in Claude Code.

### 7. Measure and trim

Count words and lines, in total and per section. Stay under 500 lines. Cut what the model already knows, anything said twice, and reasoning longer than a clause. Stop when the next cut would remove a rule.

### 8. Align with sibling skills

Skills that work together use one word per idea. A word with two meanings gets a definition or a rename. Read the sibling skills first and use their words; this is the vocabulary to keep unless the user's skills say otherwise:

| Word | Meaning |
|---|---|
| finding | One item in an audit: a reference and its severity, then **Proof**, **Confidence** and **Fix** |
| proof | What shows a finding is real: a `path:line`, a commit, a PR, a doc |
| confirmed / likely | Checked, or could not be checked (say what to verify) |
| blocks / slows / minor | The severity scale, with a one-line definition in each skill |
| "No findings" | The empty result, followed by the list of what was audited |
| stale | No longer matches the code |
| go-ahead | The user's approval, awaited before anything public or irreversible |
| fresh session with no context | The reader a skill, an issue or a Claude-facing doc is written for |
| waits on / ready | Order between pieces of work; ready means it waits on nothing open |
| subagent | A worker another session spawns; "agent" is for a repo's agent files |

Keep a repo's own words (a reviewer agent's severity names, say) when quoting that repo. Trigger words such as "outdated" or "drift" may stay in a description so the skill still loads.

### 9. Save and confirm

Read the saved version in full first; saving replaces the whole file. Save through whatever the session provides: a proposal card where one exists, otherwise the `SKILL.md` in the skills folder. Then check what is actually saved.

Deliver with:

- What each part is based on
- What you added yourself
- What is untested
- The word and line count
- A first test that only reads and reports

## Auditing a skill

Read the whole skill, then research online as in step 4: the official documentation, similar skills and existing solutions. Check the skill against those and against its real use. Change nothing yet.

- **Dangling references**: memory, files or examples the reader may not have.
- **Claims**: each command, API call and platform behaviour, as in step 5.
- **Real outputs**: read two things the skill produced or should have produced, as raw text. If the skill has never run, say so, or do a read-only dry run. Note patterns they share that the skill never states, and rules they do not follow.
- **Missing shape**: no template, no empty case, no scope rule, a placeholder left unfilled.
- **Missing gate**: a public or irreversible action with no go-ahead.
- **Order and recovery**: a step that needs what a later step provides; no path for a run that stopped halfway.
- **Guesswork**: a check based on what is usual instead of on the repo flags deliberate choices as faults.
- **Name and description**: they match the behaviour, contain the words that should load it, and follow step 6.
- **Overlap**: read the descriptions of the sibling skills and the installed plugin skills. A request that fits two descriptions needs a boundary line in one or both.
- **Argument placeholders**: Claude Code replaces `\$ARGUMENTS`, `\$0`, `\$1`… with the arguments whenever a skill is called with any, including inside code blocks and dollar amounts. To keep one literal, put a backslash directly before its dollar sign; Claude Code removes the backslash, with or without arguments. In awk, `$(0)` also works.
- **Duplication**: rules copied from elsewhere.
- **Terminology** that differs from the vocabulary in step 8 or from its sibling skills.
- **Padding**: explanations the model does not need.

Also note what the skill gets right, so a rewrite keeps it.

**Output.** First line: the skill, its word and line count, and what you checked it against. Then findings, most severe first:

- The section or line (**severity**): what is wrong, in one sentence
- **Proof**: the doc, real output or line that shows it
- **Confidence**: confirmed (checked) or likely (could not be checked; say what to verify)
- **Fix**: one sentence, naming what to change: the skill, or the thing it describes

Severity: **blocks** (a fresh session cannot complete the task, or does harm), **slows** (it loses time or has to guess), **minor**. Only report what you can point to. If nothing qualifies, say "No findings".

Follow with a table of the similar skills and solutions and what each does that this one does not, the list of sources with links, then a recommendation.

**Then wait for a go-ahead.** When rewriting, keep the name so references to it still work, keep what it got right, and deliver as in step 9 with each change tied to its finding.