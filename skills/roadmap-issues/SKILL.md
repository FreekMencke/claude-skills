---
name: "roadmap-issues"
description: "Create, audit or refresh a GitHub roadmap issue with ordered sub-issues and blocked-by links, across repos. Use when work is split over several issues, when asked for a roadmap, a tracking issue or to break work into issues, or to check whether an existing roadmap and its children are stale."
---

# Roadmap issues

A roadmap is one GitHub issue that splits a piece of work over several child issues, fixes their order, and holds the context they share. It lives in the repo where most of the work is. Reference examples (public): `osrs-tracker/osrs-tracker-web#159`, `osrs-tracker/osrs-tracker-aws#52`.

This skill writes and maintains the issues. Carrying them out is the `parallel-code-orchestrator` skill's job. A single follow-up in another repo needs one issue in the child format below, not a roadmap.

To check an existing roadmap, go to "Audit an existing roadmap".

## Rules that apply throughout

- **Read other repos, never change them.** Read the target repo so each issue is accurate; changes there happen in a fresh session that picks the issue up.
- **Same owner.** GitHub only accepts a sub-issue with the same owner as its parent. A child under another owner is a normal issue linked from the roadmap body.
- **Public repos**: no account, resource or cluster IDs anywhere, including pasted evidence.
- **Labels**: `enhancement` (or the fitting type) on every issue, `question` on a child that investigates or decides, plus `cross-repo` on issues raised from another repo's session. Use only labels that exist in the target repo; GitHub drops a label it cannot apply without an error, so check `.labels` in the response.
- **Never guess issue numbers.** Other sessions open issues too; a number is yours only once GitHub returns it.
- **Order words.** A child "waits on" another issue; it is "ready" when it waits on nothing open. "Blocked-by link" means only GitHub's dependency feature.

## 1. Plan and get a go-ahead

Search the open issues for an existing roadmap on the topic first, and resume it if there is one.

Draft the roadmap title, then per child: repo, title (`<Area>: <what changes>`), one line, what it waits on, and what must not merge or deploy before which step. Size a child as one session's work in one repo.

- If findings could reorder or drop children, make an "investigate first" child and mark it first.
- Put deferred ideas and open decisions in one parking child.
- A child that depends on an open decision gets `(decide first)` at the end of its title.
- A risky last step (a cutover, a migration) is its own child, last in the order.

Show the draft and wait for a go-ahead. Issues are public and cannot be taken back.

## 2. Create

Create the roadmap with a placeholder body so the children can name it. Create the children with a distinctive placeholder (such as `#TBD-3`) for each other's numbers. Then write the real numbers into every body. Create one issue at a time; GitHub rate-limits bursts. Keep each issue's number and id from the response.

```
gh api -X POST repos/<owner>/<repo>/issues -f title='...' -F body=@body.md \
  -f 'labels[]=enhancement' --jq '"\(.number) \(.id)"'
gh api -X PATCH repos/<owner>/<repo>/issues/<n> -F body=@body.md
```

`gh issue create` and `gh issue edit --body-file` do the same where they work; cloud sessions only allow the REST calls above.

### Roadmap body

Title: `Roadmap: <what> (<headline number, if there is one>)`

```
<Where this came from and when: the audit or task, the date, the commit it
was checked against. Each child stands on its own. Issues go stale: check the
steps against the current code. Load the <repo> skill first. Start with #A,
because ...>

## Order
<text diagram: what is first, what runs in parallel, what is last, and what
must not merge or deploy before which step>

### Checklist
- [ ] #A: <title> (first)
- [ ] owner/repo#B → #C: <a chain shares one line>
- [ ] #Z: <title> (last)

## <Shared context, in the sections that fit>
Design. Evidence or measurements, each with its date. How the evidence was
produced. Checked and fine. Pitfalls. Considered and dropped, with the reason.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Use full `owner/repo#N` references for children in other repos. Date the evidence: a reader months later needs to know which numbers to re-measure.

### Child body

A fresh session with no context must be able to act on it. Shared context stays in the roadmap; the child points to the section it needs.

```
Part of roadmap owner/repo#N (<short name>). <Where it sits: "Step 1;
everything else waits on this", or "Waits on owner/repo#X (published)".>
<Limits, in bold: "**Prepare a PR but don't merge it**: it merges during
owner/repo#Y.">

Load the `<repo>` skill. Issues go stale: check these steps against the
current code first.

## Problem
<what is wrong and the evidence, with file paths and lines in this repo>

## Do
1. **<The step in a few words.>** <The detail, with file paths. Include the
   specs, knock-on steps in other repos (package publishes, version bumps),
   the changelog entry and the repo's reviewer agent.>

## Don't
- <what not to do, and why>

## Verify
<the repo's verify command, then the check that shows this child is done>

## Out of scope
<what belongs to another child, with its reference>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

A child in the roadmap's own repo may write `Part of #N`. Add `Blocks owner/repo#Z` to the first paragraph when other work cannot continue without it.

Some children take a different shape:

| Child | What changes |
|---|---|
| Investigate first | Label `question`. `## Why` replaces `## Problem`. `## Do` is split into what the user does and what the session does. No `## Verify`. |
| Parking | Label `question`. `## To decide` (per item: what is known, the trade-off, a recommendation) and `## Considered and dropped`. |
| Decide first | Opens with a bold "Wait for a decision first", names the issue that decides, and says to close this one as not planned if the answer is no. |
| Risky last step | Adds `## Rollback`, and names every command that needs approval. Its last step ticks the roadmap's checklist and closes the roadmap. |

For a chain across repos (publish a package, then bump it in each consumer), write one child per repo, in order, each naming the one it waits on.

## 3. Link

In these calls the path takes an issue's number, in the repo that issue lives in. The body fields (`sub_issue_id`, `after_id`, `before_id`, `issue_id`) take its numeric `id` (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`). Make the calls one at a time; GitHub rate-limits bursts here too.

Add every same-owner child as a sub-issue, in execution order:

```
gh api -X POST repos/<owner>/<repo>/issues/<roadmap>/sub_issues -F sub_issue_id=<child id>
```

A parent takes at most 100 sub-issues, nested at most eight levels. A 422 usually means the child already has a parent; add `-F replace_parent=true` only when moving it is intended.

Move one that landed in the wrong place (`before_id` puts it ahead of another, for the first position):

```
gh api -X PATCH repos/<owner>/<repo>/issues/<roadmap>/sub_issues/priority \
  -F sub_issue_id=<child id> -F after_id=<id of the one before it>
```

Add a blocked-by link for everything a child waits on, matching the Order diagram. The path is the child's own repo and number:

```
gh api -X POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<id of the issue it waits on>
```

## 4. Check

- `gh api --paginate 'repos/<owner>/<repo>/issues/<roadmap>/sub_issues?per_page=100'` lists every child, in execution order. Without the parameters a list stops at 30.
- Each child's `.../dependencies/blocked_by` matches the Order diagram.
- No body still contains a placeholder.
- Every checklist reference points at the right issue.

Then give the user the roadmap URL and the list of children.

## Resuming and changing a roadmap

- **A session stopped halfway**: read what exists (the roadmap body, its sub-issues) and continue from there. Do not create anything twice.
- **Adding a child**: show it and wait for a go-ahead. Then create it, add it to Order and the checklist, and link it as in step 3.
- **Dropping a child**: after a go-ahead, close it as not planned with the reason, strike its checklist line, and move the reason to "Considered and dropped".

```
gh api -X POST repos/<owner>/<repo>/issues/<n>/comments -f body='<reason>'
gh api -X PATCH repos/<owner>/<repo>/issues/<n> -f state=closed -f state_reason=not_planned
```

## Audit an existing roadmap

Read the roadmap, every child, and the code they describe. Change nothing yet.

**Structure**

- The step 4 checks.
- Closed children are ticked in the checklist; open ones are not.
- The Order diagram, the checklist and the blocked-by links tell the same story.

**Each open child, against the current code**

- The file paths it names exist, and its steps still apply.
- Its `## Verify` check, or the verify step in its `## Do`, can still be run.
- No commit or merged PR since it was written has already done the work, in whole or in part.
- What it waits on is still open. If that has closed, the child is ready and the roadmap should say so.

**The roadmap body**

- Evidence: re-measure what is cheap and read-only. For the rest, flag anything the code now contradicts or that predates a change to what it measured.
- "Considered and dropped" and the pitfalls still hold.
- The "start with" advice still points at an open child.

**Output.** First line: the roadmap and the number of issues audited. Then findings, most severe first:

- `owner/repo#N`: what is stale or wrong, in one sentence
- **Proof**: the `path:line`, commit or PR that shows it
- **Confidence**: confirmed (checked against the repo) or likely (could not be checked; say what to verify)
- **Fix**: one sentence

Severity: **blocks** (following the issue as written would fail or do harm), **slows** (a session loses time or has to guess), **minor**. Only report what you can point to. If nothing qualifies, say "No findings" and list the issues audited.

**Then wait for a go-ahead before editing any issue.** When fixing:

- Correct steps, paths and links in place.
- Never overwrite evidence or a decision. Add a dated update line under it (`Update YYYY-MM-DD: ...`) so the history stays readable.
- Close a child the code has overtaken (`state_reason` `completed` or `not_planned`, as above), with the reason and the commit or PR, and update the checklist.
- Finish by running the step 4 checks again.