---
name: orion-v-top-zone-redesign
description: Redesign and audit the upper ORION V interface zone when the user says the header, top bar, labels, or overall visual hierarchy are unreadable, nameless, noisy, or visually unacceptable. Use for named-section cleanup, compact bilingual labels, top-zone hierarchy fixes, and Docker-first runtime proof of header/action/status/cockpit-top changes.
---

# ORION V Top Zone Redesign

## Goal

Turn the upper ORION V interface from a loose stack of bars into a named operator surface with clear hierarchy:
- bridge status,
- navigation,
- core systems,
- alerts,
- command line,
- cockpit quick actions.

## Read first

1. `src/qiki/services/operator_console/orion_v/app.py`
2. `src/qiki/services/operator_console/orion_v/widgets/header.py`
3. `src/qiki/services/operator_console/orion_v/widgets/action_bar.py`
4. `src/qiki/services/operator_console/orion_v/widgets/status_bars.py`
5. `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
6. `references/top-zone-principles.md`

## Non-negotiable rules

1. Every visible strip in the upper interface must have a name.
2. Do not leave generic labels like `ACTIONS` or `SKELETON` if a domain name is available.
3. Bilingual text stays compact: `RU/EN` with no spaces around `/`.
4. Do not solve readability with more text; move meaning into:
   - border titles,
   - subtitles,
   - concise button labels,
   - calmer contrast.
5. Mouse and keyboard parity must remain intact.
6. Do not add a new control path; click routes must continue to call existing actions.

## Redesign workflow

1. Audit the current upper zone.
   - Identify every strip and answer:
     - what is it called,
     - what job does it do,
     - why is its current label bad.
2. Rename the strips first.
   - `header`
   - `action bar`
   - `status bars`
   - `alerts overlay`
   - `command input`
   - `cockpit quick actions`
3. Shorten high-noise labels.
   - Prefer short nouns over descriptive sentences.
   - Put long explanations into body/help/subtitle, not into button faces.
4. Rebalance visual weight.
   - Header gets strongest identity.
   - Navigation becomes compact and clearly secondary.
   - System bars become named instrumentation, not decorative filler.
5. Prove the result.
   - Run targeted unit/UI tests.
   - Run one runtime proof or headless proof that confirms names and clickability.

## Validation

Run at least:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_header.py tests/unit/test_orion_v_status_bars.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/widgets/header.py src/qiki/services/operator_console/orion_v/widgets/action_bar.py src/qiki/services/operator_console/orion_v/widgets/status_bars.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_header.py tests/unit/test_orion_v_status_bars.py tests/unit/test_orion_v_app_incidents.py`

## Done means

1. Верхняя зона имеет именованные секции.
2. Заголовки читаются в терминале средней ширины.
3. Нет длинных шумных подписей на кнопках без необходимости.
4. Existing click behavior remains intact.
5. Proof and memory checkpoint are saved.
