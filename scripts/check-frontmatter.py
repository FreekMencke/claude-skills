#!/usr/bin/env python3
"""Check that skills/*/SKILL.md frontmatter keeps to name and description.

Skills in skills/ sync to claude.ai: a claude.ai upload fails on any key outside the Agent Skills spec, and it's not
checked whether a marketplace sync does the same (.claude/CLAUDE.md). local-skills/ may use Claude Code-only keys, so it
isn't checked.

  check-frontmatter.py           check every skills/*/SKILL.md (CI)
  check-frontmatter.py FILE...   check these files
  check-frontmatter.py --hook    PostToolUse hook: read the tool call from stdin, check the edited file if it's a
                                 skills/*/SKILL.md, and exit 2 on failure so the message goes back to Claude
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ("name", "description")
KEY = re.compile(r"^([A-Za-z0-9_-]+)\s*:")


def problems(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ["no frontmatter: the first line isn't ---"]
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return ["frontmatter has no closing ---"]
    keys = [m.group(1) for m in map(KEY.match, lines[1:end]) if m]
    found = [f"key '{key}' isn't allowed: skills/ frontmatter keeps to name and description" for key in keys
             if key not in ALLOWED]
    found += [f"key '{key}' is missing" for key in ALLOWED if key not in keys]
    return found


def is_skill(path):
    try:
        rel = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    return len(rel.parts) == 3 and rel.parts[0] == "skills" and rel.parts[2] == "SKILL.md"


def main(args):
    hook = args[:1] == ["--hook"]
    if hook:
        file_path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
        paths = [Path(file_path)] if file_path and is_skill(Path(file_path)) else []
    else:
        paths = [Path(a) for a in args] or sorted(ROOT.glob("skills/*/SKILL.md"))
    failed = False
    for path in paths:
        for problem in problems(path):
            shown = path.resolve().relative_to(ROOT) if is_skill(path) else path
            print(f"{shown}: {problem}", file=sys.stderr if hook else sys.stdout)
            failed = True
    if failed:
        return 2 if hook else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
