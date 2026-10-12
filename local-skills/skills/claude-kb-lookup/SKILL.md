---
name: claude-kb-lookup
description: "Looks up the claude-kb knowledge base on using Claude efficiently: models and effort, subagents, skills, repo agents, token usage, context and caching. Answers cite entry IDs and flag entries due for re-check. Use before choosing a subagent's model, writing an agent or skill, or cutting token cost, and for how Claude Code features behave. Not for editing the knowledge base."
---

# Look up the Claude knowledge base

The knowledge base is a git repo of sourced entries at `/home/fremen/repos/claude-kb`. Read it; never edit it.

## 1. Get the index

```bash
git -C /home/fremen/repos/claude-kb fetch -q && git -C /home/fremen/repos/claude-kb merge --ff-only -q origin/main
```

- Not `git pull`: two sessions pulling at once fail with "Cannot fast-forward to multiple branches".
- If the folder doesn't exist (a cloud session, another machine), say the knowledge base isn't available here and stop; the caller decides where to look instead.
- If the update fails, carry on with what is there and say the copy may be behind.

Then read `/home/fremen/repos/claude-kb/INDEX.md` in full, once per session. Its Quick answers table often settles the question; its index lists every entry by ID, title, type and tags.

## 2. Read only the entries you need

Pick the IDs from Quick answers or the index, usually one to four. Print each entry with its file and line:

```bash
cd /home/fremen/repos/claude-kb && for id in ORCH-005 TOK-036; do awk -v id="$id" '$(0) ~ "^## \\[" id "\\]" {p=1; print FILENAME ":" FNR; print; next} p && /^## / {exit} p' kb-*.md; done
```

Keep `$(0)`: Claude Code replaces a literal dollar-zero in a skill with the first argument when one is passed.

- An entry that says "Merged into X": read X instead.
- Follow a `Related:` ID only when the entry doesn't answer the question.
- If an ID appears in the Conflicts section of `INDEX.md`, use the side it says the sources support.
- For "what should we do" questions about our own setup, also read the "Recommendations for our setup" section of that entry's file. Recommendations go stale faster than facts.
- Stop once you have the answer. Don't read whole topic files.

## 3. Check the dates

An entry is due for re-check when its `Last verified` date is more than 60 days old. Get the cutoff with `date -d '60 days ago' +%F`; ISO dates earlier than it are due. Also note entries whose `Confidence` is `single-source` or `unverified`.

## 4. Answer

```
<the answer>

Entries: ORCH-005, ORCH-030
Due for re-check: ORCH-030 (last verified 2026-08-01); check its sources before relying on it.
Not in the knowledge base: <the part of the answer that came from elsewhere, and where from>
```

- Cite the entry ID next to each claim that comes from it.
- Leave out the "Due for re-check" and "Not in the knowledge base" lines when they're empty.
- Nothing relevant: say "The knowledge base has no entry on this", list the IDs and tags you checked, and stop. Don't fill the gap from memory as if it came from the knowledge base.

## Not this skill

- Changing, adding or re-verifying entries: work in the claude-kb repo itself, following its `CLAUDE.md`.
- Live Claude Code documentation: the `claude-code-guide` agent or the official docs.
