---
name: token-audit
description: "Measures Claude Code token spend from the local session transcripts (cost by model and category, context size, subagents, tool output, screenshots) and compares it with a baseline saved on this machine."
disable-model-invocation: true
argument-hint: "[since YYYY-MM-DD] [until YYYY-MM-DD]"
---

# Token audit

Measures what Claude Code usage costs on this machine, from `~/.claude/projects/**/*.jsonl`, and says which config
changes moved which number. The script only reads local files; nothing leaves the machine.

## 1. Run the script

`$ARGUMENTS` may give a start and end date (UTC, inclusive). Without them the script takes the last 30 days.

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/token_audit.py" --since <YYYY-MM-DD> --until <YYYY-MM-DD> --baseline
```

`--baseline` compares with `~/.claude/token-audit/baseline.json` when it exists. Add `--json` for the raw numbers.
Read the header lines first:

- **Incomplete range**: transcripts are deleted after `cleanupPeriodDays` (default 30); a warning names the earliest
  transcript when the range starts before it. Never compare totals across ranges with different day counts: use
  per-day figures and shares.
- **Not priced**: a model missing from `PRICES` in the script is reported at zero cost. Add it from
  [the pricing page](https://platform.claude.com/docs/en/about-claude/pricing) (or the `claude-api` skill), update
  `PRICES_CHECKED`, and rerun.

## 2. Compare with the baseline

The baseline is this machine's own: a range saved with `--save-baseline`, before the config changes it should judge.
It stays in `~/.claude/token-audit/`, outside every repo.

- **No baseline yet**: the script says so. Report this range's numbers and offer to save it as the baseline (rerun
  with `--save-baseline`), so later runs compare against it. Skip step 3.
- **With one**: the script prints a measure, baseline, now table of per-day figures and shares.

Cost per day also follows how much work was done, so check cost per API message before calling a drop a saving.

## 3. Say what moved and why

`~/.claude/token-audit/changes.md`, when it exists, lists the config changes made since the baseline: per change, its
date, the number that shows whether it worked, and the expected direction. Judge each one from the comparison. Without
the file, name the biggest differences and ask which changes caused them; offer to start the file with
`Date | Change | Look at | Expected` columns.

## 4. Report

- The comparison table: measure, baseline, now, change.
- One line per change in `changes.md`: worked, no effect, or too early to tell, with the number.
- The three biggest remaining costs, with evidence (the script's largest Bash outputs, the heaviest tools).
- Fixes that belong in another repo become issues there; this skill doesn't change config or code.

## Limits

- List-price estimates. On a subscription this is plan usage, not billing.
- Transcripts miss some background calls. Claude Code's own per-session `cost-state` uses the same prices but about
  10% more cache reads, so its Opus cost is about 6% higher (checked 2026-10-12). The baseline is measured the same
  way, so comparisons hold.
- Tool output is estimated at 4 characters per token. Images count once per tool result.
- One machine only: claude.ai, Cowork and other machines aren't in these files.
