# Tooling For ORION V Task + Image Audit

Use these tools selectively. The goal is not to add a heavy toolchain; it is to choose the smallest proof that answers the dispute.

## 1. Textual pilot and app testing

Best for:
- asserting screen structure
- driving key input before capture
- verifying behavior without guessing from code

Why:
- Textual's testing flow supports running apps under test and interacting with them programmatically.

Primary source:
- https://textual.textualize.io/guide/testing/

Use when:
- you need to prove a panel exists
- you need to prove button/key flow still works
- you need deterministic pre-capture setup

## 2. `pytest-textual-snapshot`

Best for:
- regression snapshots of Textual screens
- catching layout drift after a redesign pass

Why:
- the plugin saves an SVG screenshot and compares future runs against the saved snapshot.

Primary source:
- https://github.com/Textualize/pytest-textual-snapshot

Useful capabilities:
- simulate key presses before capture
- run setup code before capture
- change terminal size for layout-sensitive checks

Good fit here:
- preserving ORION V layout once a screen is accepted

## 3. Playwright screenshot comparisons

Best for:
- browser-based visual diff workflows
- image-based approval testing outside Textual itself

Primary source:
- https://playwright.dev/docs/test-snapshots

Use when:
- the workflow already exports images or HTML previews
- you need baseline image comparisons in CI

Less ideal here:
- direct TUI-first verification inside the running Textual app

## 4. Pillow `ImageChops`

Best for:
- lightweight pixel-level image difference
- ad hoc local diff scripts

Primary source:
- https://pillow.readthedocs.io/en/latest/reference/ImageChops.html

Use when:
- you already have two images
- you need a quick proof of "same vs changed"
- you want a tiny helper instead of a full browser visual-test stack

Important limit:
- pixel diffs alone do not tell you whether the operator hierarchy is correct

## Recommended selection

- For ORION V behavior + structure: Textual testing first.
- For accepted-screen regression locks: `pytest-textual-snapshot`.
- For simple image-vs-image evidence: Pillow `ImageChops`.
- For browser-style visual baselines or CI image diffs: Playwright snapshots.
