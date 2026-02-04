# RFC: Radar Visualization (Terminal-first, multi-backend, mouse + color)

**Status:** CANON (Proposed → Adopted by implementation)  
**Date:** 2026-02-04  
**Scope:** ORION Operator Console (TUI) radar visualization and operator interaction  

## 0) Summary

We need a radar visualization that is:

- **Terminal-first** (the operator runs via **SSH + tmux** on a VPS).
- **Always visible** (even when Kitty/SIXEL graphics are unavailable).
- **High-fidelity when possible** (Kitty graphics / SIXEL).
- **Interactive**: **mouse is required**, hotkeys are also required.
- **Color is required** (for IFF / danger / status).

This RFC defines a **single renderer pipeline** with multiple output backends (Unicode baseline + bitmap backends),
and a stable set of “views” (2D projections over 3D truth data) to avoid endless re-design.

## 1) Operator environment (non-negotiable)

Real runtime environment:

- Always: **SSH on VPS**
- Always: **tmux**
- Terminals vary: Warp / WezTerm / Kitty / Tabby / Termius

Implication:

- We cannot assume bitmap protocols always work end-to-end.
- Therefore **Unicode baseline renderer is mandatory**.
- Bitmap renderers are **capability upgrades**, not a different product.

## 2) Goals

1) Provide a “space awareness” view that is **useful for control**, not just pretty.
2) Keep the system deterministic and “no-mocks”:
   - If there are no tracks/frames: show honest empty state.
3) Allow gradual improvement without rewriting the whole UI:
   - One data model → multiple views → multiple output backends.

## 3) Non-goals (for Phase 1)

- Web visualization (browser sidecar) — **explicitly not planned**.
- Full 3D shaded rendering / GPU pipeline.
- Perfect terminal compatibility for every client/escape-path; we do best-effort with fallbacks.

## 4) Single data model (3D truth) + multiple views (2D projections)

We lock the “space model” to avoid debate:

- Data is 3D: `x, y, z` (simulation truth).
- UI provides multiple **2D views** (projections/slices) derived from that:
  - **Top (XY)** — primary “situational awareness” / classic PPI-like.
  - **Side (XZ)** — altitude/vertical separation awareness.
  - **Front (YZ)** — approach/closing awareness.
  - **ISO** (pseudo-3D) — pseudo-3D projection with yaw/pitch camera (available).

Rationale: 3D truth, but 2D views are debuggable and legible in terminals.

## 5) Renderer architecture (one pipeline, multiple backends)

### 5.1 Pipeline layers

1) **Scene building** (pure logic, no terminal I/O):
   - Input: tracks + guard overlays + camera/view config.
   - Output: a normalized “scene” (primitives).
2) **Projection**:
   - Convert 3D primitives to 2D primitives for a given view.
3) **Rasterization / glyphization**:
   - Produce either:
     - a **Unicode canvas** (cells + colors), or
     - an **RGBA bitmap** (for Kitty/SIXEL).
4) **Backend output**:
   - Unicode backend: Textual widgets with styled text.
   - Bitmap backend: image widget (Kitty/SIXEL) inside Textual.

### 5.2 Backends

Backends are ordered by preference, but runtime chooses the best available:

1) **Unicode renderer (MANDATORY)**:
   - Uses braille/blocks/box drawing for dense graphics.
   - Uses truecolor when available; degrades to limited palette otherwise.
   - Must work over SSH+tmux consistently.
2) **Kitty graphics (BEST)**:
   - High quality, high FPS potential.
   - Works best on local Kitty/WezTerm; may fail over tmux/SSH depending on passthrough.
3) **SIXEL (SECOND BEST)**:
   - Similar benefits; availability varies by terminal and configuration.

We keep all of these in a single UX: same controls, same legends, same overlays.

## 6) Interaction model (mouse + hotkeys)

### 6.1 Mouse (required)

- Wheel: zoom in/out.
- Left click: select nearest track (within pick radius).
- Left drag:
  - In Top/Side/Front views: pan (translate viewport).
  - In ISO view: rotate yaw/pitch (use `radar.iso reset` to reset).
- Right click: context action (future; starts as “clear selection”).

### 6.2 Hotkeys (required)

- Switch view: Top/Side/Front/ISO.
- Reset camera.
- Cycle selection (next/prev track).
- Toggle overlays (guard zones, vectors, labels).

## 7) Visual language (color + symbols)

Color is mandatory and is used consistently:

- IFF: Friend / Foe / Unknown
- Track status: New / Tracked / Coasting / Lost
- Severity overlays: guard warnings/critical rules

The legend is always visible (compact) and can be expanded in an inspector panel.

## 8) Overlays and information density

The radar is not only dots:

- Track glyph + ID label (optional/zoom-dependent)
- Velocity vector
- Range rings / grid
- Guard zones boundaries (derived from guard rules)
- Alerts highlighting (e.g., unknown close contact)

Rule: detail increases with zoom (LOD), to avoid clutter.

## 9) Performance policy

- Target refresh: **5–10 Hz**.
- Adaptive degradation:
  - If render time exceeds budget, reduce:
    - update frequency,
    - label density,
    - bitmap resolution (for Kitty/SIXEL).

## 10) Configuration surface (canonical knobs)

Runtime controls (canonical names; implementation may start as env vars):

- `RADAR_RENDERER=auto|unicode|kitty|sixel`
- `RADAR_VIEW=top|side|front|iso`
- `RADAR_FPS_MAX=10`
- `RADAR_THEME=...`
- `RADAR_COLOR=1` (on by default)

### 10.1 Operator procedure (safe defaults)

**Default safety rule:** if you are in **SSH+tmux** (the canonical Phase1 operator environment), keep the radar on the **Unicode baseline**.

Enable bitmap backends only when you have proven terminal passthrough end-to-end:

- `RADAR_RENDERER=unicode` — always-safe baseline (Braille/blocks, works in SSH+tmux).
- `RADAR_RENDERER=auto` — enables **bitmap only** when the terminal supports a true bitmap protocol (Kitty TGP / SIXEL); otherwise stays on the Unicode baseline.
- `RADAR_RENDERER=kitty` — force Kitty Terminal Graphics Protocol (local Kitty/WezTerm; avoid SSH+tmux unless proven).
- `RADAR_RENDERER=sixel` — force SIXEL (only on terminals that support it).

In the Phase1 Docker stack, these env vars (`RADAR_RENDERER`, `RADAR_VIEW`) are passed to `operator-console` via `docker-compose.operator.yml`.

## 11) Dependencies (allowed and expected)

We allow adding dependencies for radar graphics:

- `Pillow` for bitmap drawing (rings, points, vectors).
- `textual-image` for terminal image protocols (Kitty/SIXEL) inside Textual.

Unicode backend must not depend on these being present to function logically,
but the product installation may include them in Docker images for simplicity.

## 12) Acceptance criteria (for implementation)

### 12.1 Baseline (must pass)

- Works in SSH+tmux on a minimal terminal with Unicode support.
- Color encoding for IFF/status is visible.
- Mouse wheel zoom works.
- Click selection works.
- Views (Top/Side/Front/ISO) exist and are switchable.
- Empty state is honest (no mocked tracks).

### 12.2 Enhanced (when supported)

- Auto-detect selects Kitty or SIXEL backend when available.
- Fallback to Unicode is seamless when graphics is unavailable.
