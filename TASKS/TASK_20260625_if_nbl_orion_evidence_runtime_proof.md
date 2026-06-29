# TASK: IF-NBL ORION Evidence Docker runtime proof

**ID:** TASK_20260625_if_nbl_orion_evidence_runtime_proof
**Status:** in_progress
**Owner:** Codex / Claude / sonra44
**Date created:** 2026-06-25

## Goal

Close the IF-NBL / ORION Evidence interface slice with Docker-first runtime proof, not only committed files or local unit tests.

## Operator Scenario (visible outcome)

- Who performs: operator / developer
- ORION-visible outcome:
  F8 opens ORION Evidence read-only and shows the NBL card honestly as not implemented / target-only, with canonical reason codes and missing/unknown fields shown explicitly.
- Constraint: this cycle proves the interface/runtime visibility of the target-only evidence card. It does not implement a real NBL packet controller.

## Reproduction Command

    docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console
    docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_nbl_evidence_adapter.py tests/unit/test_evidence_card_view.py tests/unit/test_evidence_screen_mount.py tests/unit/test_orion_v_app_incidents.py::test_evidence_level_renders_nbl_card_from_live_snapshot tests/unit/test_orion_v_action_bar.py::test_action_bar_uses_compact_labels_for_dense_console_layout
    docker exec -i qiki-operator-console python - <<'PY'
    import asyncio
    from qiki.services.operator_console.orion_v.app import OrionVApp
    from qiki.services.operator_console.orion_v.screens.evidence_stream import OrionVEvidenceScreen
    from qiki.services.operator_console.orion_v.widgets.evidence_card_view import OrionVEvidenceCard

    async def main():
        async def no_nats(self):
            self._nats_state = "lost"
        OrionVApp._connect_and_subscribe = no_nats
        app = OrionVApp()
        app._snapshot = {"power": {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0}}
        async with app.run_test(size=(140, 44)) as pilot:
            await pilot.pause()
            app.action_show_level("f8")
            await pilot.pause()
            evidence = app.query_one("#orionv-evidence", OrionVEvidenceScreen)
            cards = evidence.query(OrionVEvidenceCard)
            rendered = str(cards.first().render()) if len(cards) else ""
            print("evidence_hidden", evidence.has_class("hidden"))
            print("cards", len(cards))
            print("has_NBL_NOT_IMPLEMENTED", "NBL_NOT_IMPLEMENTED" in rendered)
            print("has_NBL_RULES_ONLY", "NBL_RULES_ONLY" in rendered)
            print("has_NBL_PDU_DENIED", "NBL_PDU_DENIED" in rendered)

    asyncio.run(main())
    PY
    docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml logs --since=3m operator-console | grep -E 'Traceback|ERROR|Exception|NoMatches|ImportError' || true

## Before / After

- Before:
  Commit d12dab5 recorded data+card+screen, not wired yet, while later F8 wiring lived in the dirty worktree and was not centered around Docker runtime proof.
- After:
  The Docker operator-console service is healthy; targeted Docker tests pass; an in-container Textual harness opens F8 Evidence and verifies the NBL card and reason codes; HERDR live pane shows F8 Evidence.

## Impact Metric

- Metric: interface/runtime gates with proof
- Baseline:
  2/5 gates were clear: qiki-dev tests and code files, but operator runtime proof was not centered.
- Target:
  5/5 gates: Docker service healthy, targeted tests green, in-container F8 harness green, live pane visible, logs clean.
- Actual:
  5/5 as of 2026-06-25 runtime proof below. Repo still has unrelated dirty files; commit/cleanup remains a separate closeout step.

## Scope / Non-goals

- In scope:
  - prove F8 Evidence wiring in Docker runtime
  - prove NBL card remains target-only / read-only
  - record the proof in a task dossier
  - keep ORION V as the production operator surface
- Out of scope:
  - implementing a real NBL packet controller
  - claiming QIKI Body runtime conformance
  - touching unrelated visual artifacts or AGENTS backups

## Canon links

- Priority board (canonical): ~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md
- Related docs/code:
  - docs/design/hardware_and_physics/qiki_body_v0_2_2/06_INTERFACE_CONTROL.md
  - src/qiki/services/operator_console/orion_v/evidence_adapters.py
  - src/qiki/services/operator_console/orion_v/evidence_card_vm.py
  - src/qiki/services/operator_console/orion_v/screens/evidence_stream.py
  - src/qiki/services/operator_console/orion_v/widgets/evidence_card_view.py
  - src/qiki/services/operator_console/orion_v/app.py
  - tests/unit/test_nbl_evidence_adapter.py
  - tests/unit/test_evidence_card_view.py
  - tests/unit/test_evidence_screen_mount.py
  - tests/unit/test_orion_v_app_incidents.py
  - tests/unit/test_orion_v_action_bar.py

## Plan (steps)

1) Prove Docker service health.
2) Prove targeted Docker tests.
3) Prove F8 Evidence inside the running operator-console image/container.
4) Prove live ORION pane visibility.
5) Record proof and leave the next closeout step explicit.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Операционный сценарий воспроизводится по команде из Reproduction Command
- [x] Есть измеримый Impact Metric (baseline -> actual)
- [x] Logs checked for tracebacks/errors
- [ ] Commit/dirty-tree closeout completed
- [ ] Repo clean (git status --porcelain is expected)

## Evidence (commands -> output)

- docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console
  - qiki-operator-console ... Up 47 seconds (healthy)
- docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q ...
  - 13 passed
- docker exec -i qiki-operator-console python - ...
  - evidence_hidden False
  - cards 1
  - has_NBL_NOT_IMPLEMENTED True
  - has_NBL_RULES_ONLY True
  - has_NBL_PDU_DENIED True
  - EXIT:0
- HERDR live pane w1:p3
  - ORION Evidence read-only
  - NBL не реализовано / target-only
  - причина: NBL_NOT_IMPLEMENTED, NBL_RULES_ONLY
  - action rail includes F8 Evid
- docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml logs --since=3m operator-console | grep -E 'Traceback|ERROR|Exception|NoMatches|ImportError' || true
  - empty output

## Notes / Risks

- RAG-gate verdict (2026-06-25):
  - Canon says: QIKI Body v0.2.2 06_INTERFACE_CONTROL.md is interface control / target-only / documentation-only; runtime conformance is not claimed by docs alone.
  - Canon §17 says: IF-NBL-001 blocked states include not_implemented and rules_only; reason_codes include NBL_PDU_DENIED, NBL_NOT_IMPLEMENTED, NBL_RULES_ONLY; ORION evidence must show criticality, payload class, cost, status, delivery uncertainty, and reason_codes; status is rules-only / target-only.
  - Code says: snapshot_to_nbl_record reads real snapshot power-budget facts, keeps packet fields missing/unknown, returns status not_implemented, always includes NBL_NOT_IMPLEMENTED and NBL_RULES_ONLY, and adds NBL_PDU_DENIED when power.nbl_allowed is false.
  - Runtime proof says: Docker operator-console can open F8 Evidence and shows one read-only NBL card with the canonical reason codes. No semantic fix is needed for IF-NBL target-only behavior; the remaining fix is closeout hygiene around dirty wiring, board/status, and memory proof.
- The live Docker log can render at narrow width and omit F8 from the visible action-rail text even when the in-container app and wider live pane prove F8. Do not use a clipped 80-column log as the sole interface proof.
- Commit d12dab5 truthfully says not wired yet; current dirty worktree contains the F8 wiring. Closeout must either commit the wiring or explicitly park it. Do not claim the committed slice alone contains the full runtime proof.

## Next

1) Commit or otherwise close the F8 wiring dirty files as a separate clean step.
2) Save STATUS / TODO_NEXT / DECISIONS with recall proof after final closeout.
