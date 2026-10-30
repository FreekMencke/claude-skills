---
name: handoff
description: "Writes a handoff of this session (goal, state, changes, decisions, dead ends, next steps) to the open PR or issue, or a scratch file, so a fresh session can continue after /clear."
disable-model-invocation: true
argument-hint: "[what the next session should focus on]"
---

# Handoff

Long sessions re-read their whole context on every turn. Auto-compaction shrinks it to a summary in a fixed format,
which keeps no file contents and may drop a dead end. A handoff written on purpose keeps the decisions and dead ends,
and lets a fresh session pick up after `/clear` for the cost of reading one note.

If `$ARGUMENTS` is set, it says what the next session should focus on: put it first under **Next steps**.

## When not to hand off

A handoff is for a context that is full or confused as a whole. Three cases have cheaper fixes that keep the good
context:

- **Long but on track**: let it compact. Measured over 31 auto-compactions at a 400k window, none lost context a
  session then needed; the next turns re-read the files they edit.
- **One bad detour**: rewind (`Esc Esc` or `/rewind`, then **Restore code and conversation**) to the prompt before it,
  and edit that prompt with what you learned.
- **An alternative worth trying**: `/branch` copies the conversation and leaves the original to `/resume`. It copies
  the conversation, not the files: pair it with a commit or a worktree for a code experiment. Desktop WSL sessions
  have no `/branch` (no session forking).

If the conversation looks like one of these, say which in one line and ask before writing the handoff.

## 1. Collect the state

Check, don't recall:

- `git status --short`, `git branch --show-current`, `git log --oneline -5`, and `git worktree list` when in a worktree
- The open PR for this branch: `gh pr view --json number,url,state,headRefName` (no PR is fine)
- The issue the work belongs to: from the PR's closing references, the branch name or the conversation
- Background work still running: subagents, background shells, monitors. They report only to this session and are
  lost on `/clear`.
- The verify command and its last result from this session. Don't rerun slow checks for the handoff; if it never ran,
  say so.

If background work is still running, say so and stop: tell the user to wait for it, or to compact instead of clearing.
Don't write the handoff yet.

## 2. Write the handoff

Self-contained: the reader has no memory of this session. Full references (`owner/repo#N`, commit SHAs, absolute
paths), no "as discussed". Leave out anything the reader can get from the code or `git log`.

```markdown
## Handoff <YYYY-MM-DD HH:MM>

**Goal and done-when**: <the task, and the check that shows it's finished>

**State**: repo <path>, branch <name> at <sha> (<pushed / not pushed>), worktree <path if any>.
<Uncommitted changes, if any, and whether they're meant to be kept.> PR <ref and state>, issue <ref>.

**Changed so far**
- <file or area>: <what and why>

**Decisions**
- <decision>: <why; what it rules out>

**Tried and dropped**
- <approach>: <why it failed, so it isn't retried>

**Verify**: `<command>`: <last result, with date>

**Next steps**
1. <step>: <its done-when>

**Open questions**
- <question, and who decides>
```

Drop sections that would be empty. Keep it under about 60 lines; link to long output instead of pasting it.

## 3. Put it where the next session will look

- **Open PR for this branch**: post it as a PR comment (`gh pr comment <n> --body-file <file>`).
- **Otherwise an issue the work belongs to**: post it as an issue comment.
- **Otherwise**: write it to `handoff-<YYYY-MM-DD-HHMM>.md` in the session's scratchpad directory, or in `/tmp` when
  there is none. These don't survive a reboot; for work that spans days, open an issue and post the handoff there.

A comment on a public repo is public: no secrets, tokens, account, resource or cluster IDs.

## 4. Tell the user what to run

End with exactly this, filled in:

> Handoff written to <link or path>. Run `/clear <short name>`, which names this session so `/resume` can find it,
> then start with: `continue from <link or path>`

In the desktop app, which has no `/resume` in WSL sessions, end with this instead:

> Handoff written to <link or path>. Start a new session (**+ New session**, or Ctrl+N) on the same folder and begin
> with: `continue from <link or path>`. This session stays in the sidebar.

Uncommitted changes stay in the working tree across `/clear`; say so if there are any, and in the desktop app name the
worktree they are in, since a new session may start in a new worktree.
