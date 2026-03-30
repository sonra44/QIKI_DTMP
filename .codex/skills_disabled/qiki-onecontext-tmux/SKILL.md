---
name: qiki-onecontext-tmux
description: Launch and operate OneContext for QIKI_DTMP through a dedicated tmux-hosted TUI window named ONE. Use when history/context lookup is needed and shell-only onecontext commands are unavailable outside the OneContext environment.
---

# QIKI_DTMP — OneContext over tmux

## Goal

Use `OneContext` reliably as a **tmux-hosted TUI**, not as a shell-only CLI.

This skill exists because:
- `onecontext context show` / `onecontext search` may fail outside the OneContext environment;
- the proven runtime path is a dedicated tmux window `ONE` operated via `tmux capture-pane` and `tmux send-keys`.

## When to use

Use this skill when:
- the user asks for past context, previous decisions, history, or “what did we do before?”;
- `onecontext` shell commands are unavailable outside their own environment;
- you need to bootstrap or reuse the live OneContext pane safely.

## Canonical workflow

1) Confirm tmux access:
   - `tmux list-sessions`

2) Reuse existing `ONE` window if present; otherwise create it:
   - `tmux list-windows -t <session> -F '#{window_index}:#{window_name}'`
   - if missing:
     - `tmux new-window -t <session>: -n ONE 'bash -lc "onecontext"'`

3) Find the pane and prove it is really OneContext:
   - `tmux list-panes -t <session>:<window> -F '#{pane_id} active=#{pane_active} alt=#{alternate_on} mouse=#{mouse_any_flag} cmd=#{pane_current_command}'`
   - `tmux capture-pane -p -t <pane_id> -S -120`

Expected proof:
- `alternate_on=1`
- `mouse_any_flag=1`
- `cmd=python`
- visible `OneContext` TUI, not a shell prompt

4) Before any risky navigation, open help once:
   - `tmux send-keys -t <pane_id> '?'`
   - capture again

Known shortcuts proven in runtime:
- `Tab` / `Shift-Tab`
- `n` / `p`
- `Enter`
- `Space`
- `c`
- `l`
- `y`
- `s`
- `r`
- `?`

5) Close help and continue with capture-first discipline:
   - always `capture-pane` before sending more keys
   - prefer non-destructive navigation keys first

## Guardrails

- Do **not** treat failed shell-only `onecontext` commands outside its environment as a product bug.
- Do **not** send keys blindly; always capture first and verify the target screen.
- Do **not** assume selection state is text-visible. If list navigation is not observable via capture, stop short of destructive actions and ask the user for one precise manual selection step.
- Do **not** store secrets, auth material, or raw private history dumps in memory/handoff.

## Output format

When using this skill, report only:
- `ONE` window target (`session:window.pane`)
- whether OneContext is live and readable
- what was proven controllable
- the next history step you can take safely

## Current proven runtime evidence

On 2026-03-07 this path was proven live on:
- tmux target `1:4.0`
- pane `%30`
- `alternate_on=1`
- `mouse_any_flag=1`
- help overlay readable through `capture-pane`
