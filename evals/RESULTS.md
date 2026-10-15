# Trigger eval results

Latest run per skill, for the cases in `evals/` and `local-skills/evals/`: runs that loaded the skill / skipped it,
3 runs per case, Opus 5.5. After a rerun, replace that skill's row; git history keeps the old numbers.

| Skill | Cases (load + near miss) | Should load | Near miss skipped | Claude Code | Date |
|---|---|---|---|---|---|
| `roadmap-issues` | 5 + 5 | 15/15 | 15/15 | 2.1.296 | 2026-10-15 |
| `parallel-code-orchestrator` | 3 + 3 | 9/9 | 9/9 | 2.1.296 | 2026-10-12 |
| `refresh-md-files` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-12; `skips-5` 2026-10-14 |
| `skill-workshop` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-15 |
| `seo-audit` | 4 + 4 | 12/12 | 12/12 | 2.1.296 | 2026-10-13; `skips-4` 2026-10-15 |
| `tech-debt-audit` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-15 |
| `research` | 4 + 4 | 12/12 | 12/12 | 2.1.296 | 2026-10-15 |
| `angular-conventions` | 4 + 5 | 12/12 | 15/15 | 2.1.296 | 2026-10-14 |
