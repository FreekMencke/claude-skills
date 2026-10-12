---
name: token-audit
description: "Measures Claude Code token spend from the local session transcripts (cost by model and category, context size, subagents, tool output, screenshots) and compares it with the 2026-10 baseline."
disable-model-invocation: true
argument-hint: "[since YYYY-MM-DD] [until YYYY-MM-DD]"
---

# Token audit

Measures what Claude Code usage costs on this machine, from `~/.claude/projects/**/*.jsonl`, and says which config
changes moved which number. The script only reads local files; nothing leaves the machine.

## 1. Run the script

`$ARGUMENTS` may give a start and end date (UTC, inclusive). Without them the script takes the last 30 days.

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/token_audit.py" --since <YYYY-MM-DD> --until <YYYY-MM-DD>
```

Add `--json` for the raw numbers. Read the header lines first:

- **Incomplete range**: transcripts are deleted after `cleanupPeriodDays` (default 30), and none exist before
  2026-10-06. Never compare totals across ranges with different day counts: use per-day figures and shares.
- **Not priced**: a model missing from `PRICES` in the script is reported at zero cost. Add it from
  [the pricing page](https://platform.claude.com/docs/en/about-claude/pricing) (or the `claude-api` skill), update
  `PRICES_CHECKED`, and rerun. `<synthetic>` lines carry no usage and can be ignored.

## 2. Compare with the baseline

Measured with this script over 2026-10-07 to 2026-10-11 (5 days, 197 sessions), the last days before the config
changes of 2026-10-12. claude-kb TOK-008 has the same numbers, measured by hand; its "30 days" was really these days.

| Measure | Baseline |
|---|---|
| Cost per day with data | 186 USD (list price) |
| Cost split | cache read 53%, cache write 29%, output 18%, input 0% |
| Cost by model | Opus 5.5 93%, Fable 5.1 5%, Sonnet 5.5 2%, Haiku 0% |
| Subagents | 13% of cost: Opus 48%, Fable 39%, Sonnet 14%, Haiku 0% of subagent cost |
| Context per API message, turns / input tokens | <100k 42/17%, 100–200k 34/30%, 200–400k 17/30%, >400k 7/23% |
| Peak context per session | p50 109k, p90 307k, max 759k; 35% of sessions over 150k; 1 compaction |
| Bash output | 1.17M tokens per day, avg 507 per call; calls over 3k tokens: 4% of calls, 33% of volume |
| Images in tool results | 146 per day |

## 3. Say what moved and why

Each change made on 2026-10-12, and the number that shows whether it worked:

| Change | Look at | Expected |
|---|---|---|
| Explore on Haiku 5.5 (`~/.claude/agents/explore.md`) | Haiku share of subagent cost and tokens | Up from 0% |
| `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` | Sonnet share of subagent cost | Up from 14%; Opus share down |
| `autoCompactWindow: 400000` + compact instructions | >400k turns, max peak, compactions | >400k near 0%; max about 400k; more compactions |
| Shell-output habits in the global CLAUDE.md | Bash tokens per day, avg per call, >3k share | Down |
| `parallel-code-orchestrator` model and effort table | Subagent cost by model | Fewer Opus subagents |
| `/handoff` before `/clear` | 200–400k turns, peak p90 | Down |
| Screenshot hygiene (osrs-tracker/osrs-tracker-web#223) | Images per day | Down once that issue is done |

Cost per day also follows how much work was done, so check cost per API message (printed next to the total;
baseline 0.059 USD) before calling a drop a saving.

## 4. Report

- A table: measure, baseline, now, change.
- One line per change above: worked, no effect, or too early to tell, with the number.
- The three biggest remaining costs, with evidence (the script's largest Bash outputs, the heaviest tools).
- Fixes that belong in another repo become issues there; this skill doesn't change config or code.

## Limits

- List-price estimates. On a subscription this is plan usage, not billing.
- Transcripts miss some background calls. Claude Code's own per-session `cost-state` uses the same prices but about
  10% more cache reads, so its Opus cost is about 6% higher (checked 2026-10-12). The baseline was measured the same
  way, so comparisons hold.
- Tool output is estimated at 4 characters per token. Images count once per tool result.
- One machine only: claude.ai, Cowork and other machines aren't in these files.
