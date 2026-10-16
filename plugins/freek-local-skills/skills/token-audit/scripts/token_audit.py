#!/usr/bin/env python3
"""Measure Claude Code token spend from the local transcripts in ~/.claude/projects.

Reads only local files and prints a report; nothing is sent anywhere. Costs are list-price
estimates (on a subscription they are plan usage, not billing).

Method: one API message can span several transcript lines, so assistant
usage is deduplicated by message.id, keeping the last line. Tool output is estimated at
4 characters per token.
"""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import statistics
import sys

# USD per million tokens: input, 5m cache write, 1h cache write, cache read, output.
# Source: platform.claude.com/docs/en/about-claude/pricing, checked 2026-10-12.
PRICES = {
    "claude-fable-5-1": (10.0, 12.5, 20.0, 0.25, 50.0),
    "claude-opus-5-5": (4.0, 5.0, 8.0, 0.20, 20.0),
    "claude-sonnet-5-5": (2.0, 2.5, 4.0, 0.10, 10.0),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),  # prompts up to 100k tokens
    "claude-haiku-5-5>100k": (0.50, 0.625, 1.0, 0.05, 2.50),  # prompts over 100k tokens
    "claude-haiku-4-5": (1.0, 1.25, 2.0, 0.10, 5.0),
}
FAST_MULTIPLIER = {"claude-opus-5-5": 2.0}  # fast mode: $8/$40 against $4/$20
PRICES_CHECKED = "2026-10-12"
CONTEXT_BUCKETS = [(0, 100_000, "<100k"), (100_000, 200_000, "100-200k"),
                   (200_000, 400_000, "200-400k"), (400_000, float("inf"), ">400k")]
CHARS_PER_TOKEN = 4
# Per machine and outside every repo: it holds this machine's usage.
DEFAULT_BASELINE = os.path.expanduser("~/.claude/token-audit/baseline.json")


def price_key(model, prompt_tokens):
    for key in PRICES:
        if model.startswith(key) and not key.endswith(">100k"):
            if key == "claude-haiku-5-5" and prompt_tokens > 100_000:
                return "claude-haiku-5-5>100k"
            return key
    return None


def message_cost(model, usage):
    """Return {category: usd} for one API message, or None for an unknown model."""
    inp = usage.get("input_tokens") or 0
    read = usage.get("cache_read_input_tokens") or 0
    write = usage.get("cache_creation_input_tokens") or 0
    out = usage.get("output_tokens") or 0
    split = usage.get("cache_creation") or {}
    w1h = split.get("ephemeral_1h_input_tokens")
    w5m = split.get("ephemeral_5m_input_tokens")
    if w1h is None and w5m is None:
        w1h, w5m = 0, write  # older lines: assume 5m writes
    key = price_key(model, inp + read + write)
    if key is None:
        return None
    p_in, p_w5, p_w1, p_read, p_out = PRICES[key]
    mult = FAST_MULTIPLIER.get(key, 1.0) if usage.get("speed") == "fast" else 1.0
    m = mult / 1_000_000
    return {
        "input": inp * p_in * m,
        "cache_read": read * p_read * m,
        "cache_write": ((w5m or 0) * p_w5 + (w1h or 0) * p_w1) * m,
        "output": out * p_out * m,
    }


def parse_day(value, end=False):
    day = dt.date.fromisoformat(value)
    t = dt.datetime.combine(day, dt.time.max if end else dt.time.min)
    return t.replace(tzinfo=dt.timezone.utc)


def parse_ts(value):
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def text_len(content):
    """Characters of text in a tool_result, and the number of images in it."""
    if isinstance(content, str):
        return len(content), 0
    chars = images = 0
    for part in content or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image":
            images += 1
        elif part.get("type") == "text":
            chars += len(part.get("text") or "")
    return chars, images


def tool_label(name):
    # mcp__plugin_playwright_playwright__browser_click -> mcp:playwright_playwright
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1].removeprefix("plugin_") if len(parts) > 2 else name
        return f"mcp:{server}"
    return name


def scan(root, since, until):
    messages = {}  # message.id -> (model, usage, is_subagent, session)
    tool_uses = {}  # tool_use id -> (name, short input)
    results = {}  # tool_use id -> (chars, images)
    prompt_images = 0
    compactions = 0
    sessions_seen = set()
    days = set()
    earliest = None
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    for path in files:
        in_subagent_dir = f"{os.sep}subagents{os.sep}" in path
        try:
            handle = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = parse_ts(rec.get("timestamp"))
                if ts is None:
                    continue
                if earliest is None or ts < earliest:
                    earliest = ts
                if not since <= ts <= until:
                    continue
                kind = rec.get("type")
                session = rec.get("sessionId") or os.path.basename(path)
                if kind == "system" and rec.get("subtype") == "compact_boundary":
                    compactions += 1
                msg = rec.get("message") or {}
                # <synthetic> messages are Claude Code's own placeholders, not API calls.
                if kind == "assistant" and msg.get("id") and msg.get("usage") and msg.get("model") != "<synthetic>":
                    subagent = bool(rec.get("isSidechain")) or in_subagent_dir
                    messages[msg["id"]] = (msg.get("model") or "?", msg["usage"], subagent, session)
                    days.add(ts.date())
                    if not subagent:
                        sessions_seen.add(session)
                    for block in msg.get("content") or []:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            inp = block.get("input") or {}
                            short = inp.get("command") or inp.get("file_path") or inp.get("url") or ""
                            tool_uses[block.get("id")] = (block.get("name") or "?", str(short))
                elif kind == "user":
                    content = msg.get("content")
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_result":
                            results[block.get("tool_use_id")] = text_len(block.get("content"))
                        elif block.get("type") == "image":
                            prompt_images += 1
    return messages, tool_uses, results, prompt_images, compactions, sessions_seen, days, earliest, len(files)


def build_report(root, since, until):
    messages, tool_uses, results, prompt_images, compactions, sessions, days, earliest, n_files = scan(root, since, until)
    cost = collections.defaultdict(lambda: collections.Counter())  # model -> category -> usd
    tokens = collections.defaultdict(lambda: collections.Counter())  # model -> category -> tokens
    sub_cost = collections.Counter()
    main_cost = 0.0
    unknown = collections.Counter()
    buckets = {label: [0, 0] for _, _, label in CONTEXT_BUCKETS}  # turns, input tokens
    peak = collections.defaultdict(int)
    for model, usage, subagent, session in messages.values():
        c = message_cost(model, usage)
        inp = usage.get("input_tokens") or 0
        read = usage.get("cache_read_input_tokens") or 0
        write = usage.get("cache_creation_input_tokens") or 0
        context = inp + read + write
        for lo, hi, label in CONTEXT_BUCKETS:
            if lo <= context < hi:
                buckets[label][0] += 1
                buckets[label][1] += context
        if not subagent:
            peak[session] = max(peak[session], context)
        t = tokens[model]
        t["input"] += inp
        t["cache_read"] += read
        t["cache_write"] += write
        t["output"] += usage.get("output_tokens") or 0
        if c is None:
            unknown[model] += 1
            continue
        cost[model].update(c)
        total = sum(c.values())
        if subagent:
            sub_cost[model] += total
        else:
            main_cost += total

    by_tool = collections.defaultdict(lambda: [0, 0, 0])  # calls, tokens, images
    bash_calls = []
    for tid, (chars, images) in results.items():
        name, short = tool_uses.get(tid, ("?", ""))
        est = chars // CHARS_PER_TOKEN
        row = by_tool[tool_label(name)]
        row[0] += 1
        row[1] += est
        row[2] += images
        if name == "Bash":
            bash_calls.append((est, short))

    bash_calls.sort(reverse=True)
    bash_total = sum(t for t, _ in bash_calls)
    big = [t for t, _ in bash_calls if t > 3000]
    peaks = sorted(peak.values())
    total_cost = sum(sum(c.values()) for c in cost.values())
    total_input = sum(b[1] for b in buckets.values())
    total_turns = sum(b[0] for b in buckets.values())
    return {
        "range": {"since": since.date().isoformat(), "until": until.date().isoformat(),
                  "earliest_transcript": earliest.date().isoformat() if earliest else None,
                  "files": n_files, "prices_checked": PRICES_CHECKED,
                  "days_with_data": len(days),
                  "first_day": min(days).isoformat() if days else None,
                  "last_day": max(days).isoformat() if days else None},
        "total_cost_usd": round(total_cost, 2),
        "cost_per_day_usd": round(total_cost / len(days), 2) if days else 0,
        "cost_by_model": {m: {k: round(v, 2) for k, v in c.items()} | {"total": round(sum(c.values()), 2)}
                          for m, c in sorted(cost.items(), key=lambda kv: -sum(kv[1].values()))},
        "tokens_by_model": {m: dict(t) for m, t in tokens.items()},
        "cost_split": {k: round(sum(c[k] for c in cost.values()), 2)
                       for k in ("cache_read", "cache_write", "output", "input")},
        "unknown_models": dict(unknown),
        "subagents": {"cost_usd": round(sum(sub_cost.values()), 2), "main_cost_usd": round(main_cost, 2),
                      "by_model": {m: round(v, 2) for m, v in sub_cost.most_common()}},
        "context_buckets": {label: {"turns": n, "input_tokens": tok} for label, (n, tok) in buckets.items()},
        "turns": total_turns,
        "input_tokens": total_input,
        "sessions": len(sessions),
        "peak_context": {
            "p50": int(statistics.median(peaks)) if peaks else 0,
            "p90": peaks[int(0.9 * (len(peaks) - 1))] if peaks else 0,
            "max": peaks[-1] if peaks else 0,
            "sessions_over_150k": sum(1 for p in peaks if p > 150_000),
        },
        "compactions": compactions,
        "tool_output": {name: {"calls": c, "est_tokens": t, "images": i}
                        for name, (c, t, i) in sorted(by_tool.items(), key=lambda kv: -kv[1][1])},
        "bash": {"calls": len(bash_calls), "est_tokens": bash_total,
                 "calls_over_3k": len(big), "share_of_volume_over_3k": round(sum(big) / bash_total, 3) if bash_total else 0,
                 "largest": [{"est_tokens": t, "command": s[:160]} for t, s in bash_calls[:10]]},
        "images": {"in_tool_results": sum(r[2] for r in by_tool.values()), "pasted_in_prompts": prompt_images},
    }


def pct(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "-"


def print_report(r):
    rng = r["range"]
    print(f"Token audit {rng['since']} to {rng['until']} (UTC), {rng['files']} transcript files, "
          f"prices checked {rng['prices_checked']}")
    if rng["earliest_transcript"] and rng["earliest_transcript"] > rng["since"]:
        print(f"WARNING: earliest transcript line is {rng['earliest_transcript']}; "
              f"nothing older exists (deleted after cleanupPeriodDays, or never recorded), so the range is incomplete.")
    total = r["total_cost_usd"]
    print(f"\nData on {rng['days_with_data']} days ({rng['first_day']} to {rng['last_day']}). "
          f"Compare per-day figures and shares, not totals, across ranges with different day counts.")
    print(f"Total list-price cost: ${total:,.2f} (${r['cost_per_day_usd']:,.2f} per day with data)   "
          f"sessions: {r['sessions']}   API messages: {r['turns']} "
          f"(${total / max(r['turns'], 1):.3f} each)")
    if r["unknown_models"]:
        print(f"Not priced (unknown model): {r['unknown_models']}")

    print("\nCost by model                 total   cache read  cache write    output    input")
    for model, c in r["cost_by_model"].items():
        print(f"  {model:<24} {c['total']:>9,.2f} {c.get('cache_read', 0):>11,.2f} {c.get('cache_write', 0):>12,.2f}"
              f" {c.get('output', 0):>9,.2f} {c.get('input', 0):>8,.2f}  ({pct(c['total'], total)})")
    split = r["cost_split"]
    print("  split: " + ", ".join(f"{k.replace('_', ' ')} {pct(v, total)}" for k, v in split.items()))
    toks = r["tokens_by_model"]
    all_toks = sum(sum(t.values()) for t in toks.values())
    print("  tokens: " + ", ".join(f"{m} {pct(sum(t.values()), all_toks)}"
                                    for m, t in sorted(toks.items(), key=lambda kv: -sum(kv[1].values()))))

    sub = r["subagents"]
    print(f"\nSubagents: ${sub['cost_usd']:,.2f} ({pct(sub['cost_usd'], total)} of cost)")
    for model, usd in sub["by_model"].items():
        print(f"  {model:<24} ${usd:>9,.2f}  ({pct(usd, sub['cost_usd'])} of subagent cost)")

    print("\nContext size per API message   turns   input tokens")
    for label, b in r["context_buckets"].items():
        print(f"  {label:<28} {pct(b['turns'], r['turns']):>6} {pct(b['input_tokens'], r['input_tokens']):>14}")
    pk = r["peak_context"]
    print(f"  peak per session: p50 {pk['p50'] // 1000}k, p90 {pk['p90'] // 1000}k, max {pk['max'] // 1000}k; "
          f"{pk['sessions_over_150k']} of {r['sessions']} sessions over 150k; compactions: {r['compactions']}")

    print("\nTool output entering context (estimated at 4 chars/token)")
    for name, t in list(r["tool_output"].items())[:12]:
        img = f", {t['images']} images" if t["images"] else ""
        print(f"  {name:<34} {t['est_tokens'] / 1e6:>6.2f}M tokens over {t['calls']:>6} calls{img}")
    b = r["bash"]
    print(f"  Bash: {b['est_tokens'] / 1e6:.2f}M tokens, {b['calls']} calls (avg {b['est_tokens'] // max(b['calls'], 1)}); "
          f"calls over 3k tokens: {pct(b['calls_over_3k'], b['calls'])} of calls, "
          f"{100 * b['share_of_volume_over_3k']:.0f}% of volume")
    print("  Largest Bash outputs:")
    for row in b["largest"]:
        print(f"    {row['est_tokens']:>7}  {row['command']}")
    im = r["images"]
    print(f"\nImages: {im['in_tool_results']} in tool results (screenshots, image reads), "
          f"{im['pasted_in_prompts']} pasted in prompts")


def measures(r):
    """Per-day figures and shares: the numbers that compare across ranges of different length."""
    days = max(r["range"]["days_with_data"], 1)
    total = r["total_cost_usd"]
    sub = r["subagents"]
    b = r["bash"]
    pk = r["peak_context"]
    m = {
        "cost per day with data": f"${r['cost_per_day_usd']:,.2f}",
        "cost per API message": f"${total / max(r['turns'], 1):.3f}",
        "API messages per day": f"{r['turns'] / days:,.0f}",
    }
    for k, v in r["cost_split"].items():
        m[f"cost split: {k.replace('_', ' ')}"] = pct(v, total)
    for model, c in r["cost_by_model"].items():
        m[f"cost share: {model}"] = pct(c["total"], total)
    m["subagents: share of cost"] = pct(sub["cost_usd"], total)
    for model, usd in sub["by_model"].items():
        m[f"subagent cost share: {model}"] = pct(usd, sub["cost_usd"])
    for label, bk in r["context_buckets"].items():
        m[f"context {label}: turns / input tokens"] = (f"{pct(bk['turns'], r['turns'])} / "
                                                      f"{pct(bk['input_tokens'], r['input_tokens'])}")
    m["peak context per session: p50 / p90 / max"] = f"{pk['p50'] // 1000}k / {pk['p90'] // 1000}k / {pk['max'] // 1000}k"
    m["sessions over 150k"] = pct(pk["sessions_over_150k"], r["sessions"])
    m["compactions per day"] = f"{r['compactions'] / days:.1f}"
    m["Bash output tokens per day"] = f"{b['est_tokens'] / days / 1e6:.2f}M"
    m["Bash avg tokens per call"] = f"{b['est_tokens'] // max(b['calls'], 1)}"
    m["Bash calls over 3k: share of calls / of volume"] = (f"{pct(b['calls_over_3k'], b['calls'])} / "
                                                          f"{100 * b['share_of_volume_over_3k']:.0f}%")
    m["images in tool results per day"] = f"{r['images']['in_tool_results'] / days:.0f}"
    return m


def print_comparison(baseline, r):
    rng = baseline["range"]
    print(f"\nAgainst the baseline of {rng['first_day']} to {rng['last_day']} ({rng['days_with_data']} days with data, "
          f"prices checked {rng['prices_checked']})")
    old, new = measures(baseline), measures(r)
    width = max(map(len, old | new))
    print(f"  {'measure':<{width}}  {'baseline':>18}  {'now':>18}")
    for key in old | new:
        print(f"  {key:<{width}}  {old.get(key, '-'):>18}  {new.get(key, '-'):>18}")


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default=(today - dt.timedelta(days=30)).isoformat(), help="YYYY-MM-DD (UTC), default 30 days ago")
    ap.add_argument("--until", default=today.isoformat(), help="YYYY-MM-DD (UTC), inclusive, default today")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"), help="transcript root")
    ap.add_argument("--json", action="store_true", help="print the raw report as JSON")
    ap.add_argument("--baseline", nargs="?", const=DEFAULT_BASELINE, metavar="FILE",
                    help=f"compare with a saved baseline (default {DEFAULT_BASELINE})")
    ap.add_argument("--save-baseline", nargs="?", const=DEFAULT_BASELINE, metavar="FILE",
                    help="save this range's report as the baseline")
    args = ap.parse_args()
    if not os.path.isdir(args.projects):
        sys.exit(f"no transcript directory at {args.projects}")
    report = build_report(args.projects, parse_day(args.since), parse_day(args.until, end=True))
    if args.save_baseline:
        os.makedirs(os.path.dirname(args.save_baseline) or ".", exist_ok=True)
        with open(args.save_baseline, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print_report(report)
        if args.save_baseline:
            print(f"\nSaved as the baseline: {args.save_baseline}")
        if args.baseline:
            if os.path.isfile(args.baseline):
                with open(args.baseline, encoding="utf-8") as f:
                    print_comparison(json.load(f), report)
            else:
                print(f"\nNo baseline at {args.baseline}; save one with --save-baseline.")


if __name__ == "__main__":
    main()
