# ADR: Radar visualization strategy (multi-backend, Unicode baseline, mouse+color)

**Status:** ACCEPTED  
**Date:** 2026-02-04  
**Decision owner:** ORION/QIKI_DTMP maintainers  

## Context

We need a radar visualization for ORION that is interactive and high-fidelity.
However, the real operator environment is:

- SSH to a VPS
- tmux
- multiple terminals (Warp / WezTerm / Kitty / Tabby / Termius)

This makes terminal image protocols (Kitty graphics / SIXEL) unreliable end-to-end.
At the same time, a “pure ASCII” radar is insufficient for the product goal (3D-ish space awareness, overlays, information density).

## Decision

1) The radar visualization is built as a **single pipeline** with multiple output backends.
2) The **Unicode high-density renderer is mandatory** and serves as the “always works” baseline in SSH+tmux.
3) Kitty graphics and SIXEL are **capability upgrades**, selected automatically when available and safe.
4) **Mouse interaction is required** (selection + zoom + drag), and hotkeys are required as well.
5) **Color is required** (IFF/status/severity), with graceful degradation when the terminal palette is limited.

The canonical specification is `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`.

## Consequences

Positive:

- Radar stays usable in the worst-case environment (SSH+tmux).
- We can still achieve a “real graphics” look on capable terminals.
- One set of controls and overlays; less product fragmentation.

Negative / costs:

- More engineering complexity than “pick one renderer and hope”.
- Requires a clear capability-detection policy and robust fallback.
- Requires more careful UX (avoid overwhelming the Unicode renderer).

## Alternatives considered

1) **Kitty-first only**
   - Rejected: breaks in a significant portion of SSH+tmux paths.
2) **SIXEL-first only**
   - Rejected: availability varies and still fails in some SSH/tmux paths.
3) **Web sidecar visualization**
   - Rejected: explicitly out of scope for this project.
4) **ASCII-only**
   - Rejected: insufficient for the intended operator experience and information density.

