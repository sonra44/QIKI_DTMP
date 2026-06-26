#!/usr/bin/env python3
"""Tool Discipline guard — Claude/Codex hook (block-lite forcing function).

Wired in Claude .claude/settings.json and Codex ~/.codex/hooks.json for:
  SessionStart     -> inject the tool doctrine + remind to run qiki_toolcheck.sh
  UserPromptSubmit -> if prompt touches canon, remind the mandatory RAG-gate
  PreToolUse(Bash) -> if a broad grep/cat/sed on src/*.py, remind Serena-first

Block-lite by design (Codex agreed): we warn / inject context, we do NOT hard-block
ordinary ops. The two hard-discipline rules (no code-claim without Serena evidence;
no canon verdict without RAG evidence) live in docs/dev/TOOL_DISCIPLINE.md and are the
agent's responsibility — hooks keep them in front of the agent at the moment of action.
"""
from __future__ import annotations

import json
import re
import sys

DOC = "docs/dev/TOOL_DISCIPLINE.md"


def emit(event: str, context: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))


def hook_event_name(data: dict) -> str:
    return str(
        data.get("hook_event_name")
        or data.get("hookEventName")
        or data.get("event")
        or data.get("hook")
        or ""
    )


def prompt_text(data: dict) -> str:
    for key in ("prompt", "user_prompt", "userPrompt", "input"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return ""


def tool_name(data: dict) -> str:
    return str(data.get("tool_name") or data.get("toolName") or data.get("name") or "")


def bash_command(data: dict) -> str:
    tool_input = data.get("tool_input") or data.get("toolInput") or data.get("input") or {}
    if isinstance(tool_input, dict):
        for key in ("command", "cmd"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    value = data.get("command") or data.get("cmd")
    return value if isinstance(value, str) else ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    event = hook_event_name(data)

    if event == "SessionStart":
        emit(
            "SessionStart",
            "TOOL DISCIPLINE ACTIVE (" + DOC + "). FIRST action this session: classify mode; "
            "for QIKI project/restore read `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md` (LIGHT) + sovereign recall FIRST. "
            "Read-only source-lookup (sovereign/LIGHT/repo/Serena/RAG): do it immediately, no permission ask. "
            "toolcheck/MCP (`bash scripts/qiki_toolcheck.sh` + one live call each) ONLY when the task needs it, not as the opening ritual. "
            "Serena find_symbol for code. RAG-gate (qiki-rag "
            "-> repo-check -> verdict) before ANY canon/IF-ORION/IF-AUDIT/vocabulary/QIKI-Body claim. "
            "herdr send = `herdr pane run`. Tools do not fire themselves — choose the right one.",
        )
        return 0

    if event == "UserPromptSubmit":
        prompt = prompt_text(data).lower()
        canon_kw = (
            "if-orion", "if-audit", "§17", "vocabulary", "qiki body", "qiki-body", "canon",
            "evidence card", "passport", "mount", "reason_code", "blackbox",
        )
        if any(k in prompt for k in canon_kw):
            emit(
                "UserPromptSubmit",
                "RAG-GATE: this touches QIKI canon. Before any canon/spec verdict, run "
                "`qiki-rag \"<query>\"` -> verify in docs/design/.../qiki_body_v0_2_2/* -> verdict "
                "(canon says X; code says Y; fix/no-fix). No canon claims from memory. " + DOC + " §4.2",
            )
        return 0

    if event == "PreToolUse" and tool_name(data) in {"Bash", "bash", "exec_command", "functions.exec_command"}:
        cmd = bash_command(data)
        if re.search(r"\b(grep|rg|sed|cat|head|tail)\b", cmd) and re.search(r"src/\S*\.py", cmd):
            reason = (
                "Serena-first: for QIKI code navigation prefer serena find_symbol / "
                "get_symbols_overview / find_referencing_symbols instead of grep/cat on src/*.py. "
                "rg/sed are an auxiliary layer, not a substitute for symbol navigation. " + DOC + " §4.1"
            )
            emit("PreToolUse", reason)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
