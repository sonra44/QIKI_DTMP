from __future__ import annotations

import asyncio
import logging
import os
import time

from textual.widgets import Static

from pathlib import Path

from qiki.services.q_core_agent.core.agent import QCoreAgent
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.services.q_core_agent.qiki_orion_intents_service import (
    _find_target_track_for_resume,
    _refresh_agent_snapshot,
)
from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.config_models import QCoreAgentConfig, load_config
from tools.orion_v_target_seed_sources import pick_initial_target_designator


logger = logging.getLogger(__name__)


def _widget_text(widget: object) -> str:
    renderable = getattr(widget, "renderable", None)
    if hasattr(renderable, "plain"):
        return str(getattr(renderable, "plain"))
    if renderable is not None:
        return str(renderable)
    content = getattr(widget, "content", None)
    if hasattr(content, "plain"):
        return str(getattr(content, "plain"))
    if content is not None:
        return str(content)
    return str(widget)


async def _wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(step_s)
    raise AssertionError(f"timeout while waiting for {label}")


async def _probe_qiki_roundtrip(app: OrionVApp) -> None:
    """Prove the QIKI request/response path before the scenario starts."""
    app._qiki_last_response = None
    app._qiki_pending_action = None
    await app._publish_qiki_intent("status")
    await _wait_until(
        lambda: app._qiki_last_response is not None,
        timeout_s=8.0,
        step_s=0.1,
        label="QIKI readiness probe",
    )
    response = app._qiki_last_response
    if response is None or response.reply is None:
        raise AssertionError("QIKI readiness probe returned no reply payload")
    app._qiki_last_response = None
    app._qiki_pending_action = None


async def _ensure_sim_running_for_live_radar(app: OrionVApp) -> None:
    sim_state = app._telemetry.get("sim_state")
    if not isinstance(sim_state, dict):
        return
    state_name = str(sim_state.get("fsm_state") or "").strip().upper()
    paused = bool(sim_state.get("paused"))
    if state_name == "RUNNING" and not paused:
        return
    await app._publish_sim_command("sim.start", {"speed": 1.0})
    if not await app._wait_for_ack("sim.start", 3.0):
        raise AssertionError("sim.start did not receive ack before waiting for live radar cache")
    await _wait_until(
        lambda: (
            isinstance(app._telemetry.get("sim_state"), dict)
            and str((app._telemetry.get("sim_state") or {}).get("fsm_state") or "").strip().upper() == "RUNNING"
            and bool((app._telemetry.get("sim_state") or {}).get("paused")) is False
        ),
        timeout_s=6.0,
        step_s=0.1,
        label="sim_state running before live radar cache",
    )


def _pick_live_target_designator_from_qcore(*, require_non_spoof: bool = False) -> tuple[str, dict[str, object]]:
    os.environ.setdefault("QIKI_ALLOW_INTERFACE_FALLBACK", "true")
    config = load_config(Path("/workspace/src/qiki/services/q_core_agent/config.yaml"), QCoreAgentConfig)
    agent = QCoreAgent(config)
    provider = GrpcDataProvider(config.grpc_server_address)
    deadline = time.monotonic() + 8.0

    while time.monotonic() < deadline:
        try:
            _refresh_agent_snapshot(agent=agent, data_provider=provider)
        except Exception:
            time.sleep(0.2)
            continue
        tracks = (agent.context.world_snapshot or {}).get("radar_tracks") or []
        if isinstance(tracks, list):
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                designator = str(
                    track.get("transponder_id") or track.get("callsign") or ""
                ).strip()
                if require_non_spoof and designator.upper().startswith("SPOOF-"):
                    continue
                if designator:
                    return designator, track
        time.sleep(0.2)

    raise AssertionError("timeout while waiting for live radar track with public designator in q_core world snapshot")


def _pick_live_target_designator(
    app: OrionVApp,
    *,
    require_non_spoof: bool = False,
) -> tuple[str, dict[str, object], str]:
    return pick_initial_target_designator(
        orion_tracks=list(app._latest_radar_tracks.values()),
        require_non_spoof=require_non_spoof,
        qcore_fallback=lambda: _pick_live_target_designator_from_qcore(require_non_spoof=require_non_spoof),
    )


def _wait_for_signature_flip_on_same_contour(
    app: OrionVApp,
    *,
    target_designator: str,
    preferred_track_id: str,
    preferred_public_track_id: str | None = None,
    previous_track_label: str,
    timeout_s: float = 8.0,
) -> tuple[dict[str, object] | None, str, str]:
    preferred_public_id = str(preferred_public_track_id or "").strip()
    deadline = time.monotonic() + timeout_s
    last_seen_label = ""
    last_seen_track: dict[str, object] | None = None

    while time.monotonic() < deadline:
        public_track = app._latest_radar_tracks.get(preferred_public_id) if preferred_public_id else None
        if isinstance(public_track, dict):
            last_seen_track = public_track
            last_seen_label = str(
                public_track.get("transponder_id") or public_track.get("id") or public_track.get("callsign") or ""
            ).strip()
            if last_seen_label and previous_track_label and last_seen_label != previous_track_label:
                return public_track, last_seen_label, "orion_live_radar_cache"
        time.sleep(0.1)

    os.environ.setdefault("QIKI_ALLOW_INTERFACE_FALLBACK", "true")
    config = load_config(Path("/workspace/src/qiki/services/q_core_agent/config.yaml"), QCoreAgentConfig)
    agent = QCoreAgent(config)
    provider = GrpcDataProvider(config.grpc_server_address)

    while time.monotonic() < deadline:
        try:
            _refresh_agent_snapshot(agent=agent, data_provider=provider)
        except Exception:
            time.sleep(0.2)
            continue
        matched_track = _find_target_track_for_resume(
            agent.context.world_snapshot,
            target_designator=target_designator,
            preferred_track_id=preferred_track_id,
        )
        if isinstance(matched_track, dict):
            last_seen_track = matched_track
            last_seen_label = str(
                matched_track.get("transponder_id") or matched_track.get("id") or matched_track.get("callsign") or ""
            ).strip()
            current_track_id = str(matched_track.get("track_id") or "").strip()
            if (
                current_track_id
                and current_track_id == preferred_track_id
                and last_seen_label
                and previous_track_label
                and last_seen_label != previous_track_label
            ):
                return matched_track, last_seen_label, "q_core_world_snapshot_fallback"
        time.sleep(0.2)
    return last_seen_track, last_seen_label, (
        "q_core_world_snapshot_fallback" if last_seen_track is not None else "timeout_without_live_signature_flip"
    )


async def _main() -> None:
    # The live operator-console service already owns the default tracks durable.
    # Use an isolated ephemeral tracks consumer for proof runs so the smoke app
    # can subscribe to the same live stream without stealing or blocking it.
    os.environ.setdefault("RADAR_TRACKS_DURABLE", "")
    observation_style = str(os.getenv("QIKI_OBSERVATION_STYLE") or "safe").strip().lower() or "safe"
    if observation_style not in {"safe", "slow"}:
        raise AssertionError(f"unsupported QIKI_OBSERVATION_STYLE={observation_style!r}")
    resume_xpdr_mode = str(os.getenv("QIKI_RESUME_XPDR_MODE") or "").strip().upper()
    if resume_xpdr_mode and resume_xpdr_mode not in {"ON", "OFF", "SILENT", "SPOOF"}:
        raise AssertionError(f"unsupported QIKI_RESUME_XPDR_MODE={resume_xpdr_mode!r}")
    initial_xpdr_mode = str(
        os.getenv("QIKI_INITIAL_XPDR_MODE") or ("ON" if resume_xpdr_mode == "SPOOF" else "")
    ).strip().upper()
    if initial_xpdr_mode and initial_xpdr_mode not in {"ON", "OFF", "SILENT", "SPOOF"}:
        raise AssertionError(f"unsupported QIKI_INITIAL_XPDR_MODE={initial_xpdr_mode!r}")
    procedure_name = "safe_pause_slow_resume" if observation_style == "slow" else "safe_pause_resume"
    command_prefix = "slow observation" if observation_style == "slow" else "safe observation"
    expected_speed = 0.25 if observation_style == "slow" else 1.0
    expected_route_ru = "медленный" if observation_style == "slow" else "безопасный"
    expected_route_role = "deviation" if observation_style == "slow" else "official"
    resume_follow_up_status = "none"
    continuation_result_status = "none"
    continued_objective_id = "none"
    continued_route_role = "none"

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await _wait_until(
            lambda: app._nats_client.connection_state == "connected",
            timeout_s=10.0,
            step_s=0.1,
            label="NATS connection",
        )
        await _wait_until(
            lambda: isinstance(app._telemetry.get("sim_state"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="sim_state telemetry",
        )
        await _wait_until(
            lambda: app._subscriptions_started and app._nats_client.active_subscriptions >= 5,
            timeout_s=10.0,
            step_s=0.1,
            label="full ORION subscriptions",
        )
        await _ensure_sim_running_for_live_radar(app)
        await _wait_until(
            lambda: bool(app._latest_radar_tracks),
            timeout_s=10.0,
            step_s=0.1,
            label="ORION live radar cache",
        )
        await _probe_qiki_roundtrip(app)
        await pilot.pause()
        if initial_xpdr_mode:
            await app._publish_sim_command("sim.xpdr.mode", {"mode": initial_xpdr_mode})
            if not await app._wait_for_ack("sim.xpdr.mode", 2.0):
                raise AssertionError("initial xpdr mode command did not receive ack before observation setup")
            await asyncio.sleep(1.0)
        target_designator, _track_snapshot, seed_source = await asyncio.to_thread(
            _pick_live_target_designator,
            app,
            require_non_spoof=(resume_xpdr_mode == "SPOOF"),
        )
        logger.info(
            "Observation seed target picked from %s: designator=%s track_id=%s label=%s",
            seed_source,
            target_designator,
            str((_track_snapshot or {}).get("track_id") or "").strip() or "missing",
            str((_track_snapshot or {}).get("transponder_id") or (_track_snapshot or {}).get("id") or "").strip()
            or "missing",
        )

        await app._publish_qiki_intent(f"{command_prefix} {target_designator}")
        await _wait_until(
            lambda: app._qiki_last_response is not None,
            timeout_s=12.0,
            step_s=0.1,
            label="QIKI response",
        )
        expected_request_id = str(app._qiki_last_response.request_id)
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("request_id") or "").strip()
                == expected_request_id
                and str((app._active_observation_objective or {}).get("observation_style") or "").strip().lower()
                == observation_style
                and str((app._active_observation_objective or {}).get("procedure_name") or "").strip() == procedure_name
            ),
            timeout_s=12.0,
            step_s=0.1,
            label="observation objective seed",
        )
        await pilot.pause()

        objective = dict(app._active_observation_objective or {})
        assert objective.get("subject") == "qiki.events.v1.operator.objectives"
        assert objective.get("status") == "prepared"
        assert objective.get("kind") == "observation_objective_seed"
        assert objective.get("observation_style") == observation_style
        assert objective.get("procedure_name") == procedure_name
        assert objective.get("route_role") == expected_route_role
        assert str(objective.get("target_designator") or "").strip().upper() == target_designator.strip().upper()
        assert objective.get("track_visible") is True
        assert objective.get("track_label") == target_designator
        assert isinstance(objective.get("track_range_m"), (int, float))
        assert isinstance(objective.get("track_quality"), (int, float))

        assert app._qiki_pending_action is not None
        assert app._qiki_pending_action["action_kind"] == "ORION_PROCEDURE"
        assert app._qiki_pending_action["name"] == procedure_name

        try:
            body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
        except Exception:
            body = ""
        if body:
            logger.info("Cockpit body snapshot captured during smoke (%s chars)", len(body))
        timeline_lines = app._build_objective_timeline_lines(app._events_store)
        if observation_style == "slow":
            await _wait_until(
                lambda: any(
                    "HIDDEN_EVENT_REVEALED" in line
                    for line in app._build_objective_timeline_lines(app._events_store)
                ),
                timeout_s=12.0,
                step_s=0.1,
                label="deviation hidden event",
            )
            timeline_lines = app._build_objective_timeline_lines(app._events_store)
            assert any("HIDDEN_EVENT_REVEALED" in line for line in timeline_lines)
        else:
            assert all("HIDDEN_EVENT_REVEALED" not in line for line in timeline_lines)

        await app._execute_qiki_pending_action()
        expected_final_qiki_status = "pending" if observation_style == "slow" else "confirmed"
        await _wait_until(
            lambda: (
                app._qiki_last_response is not None
                and app._qiki_last_response.consequence is not None
                and app._qiki_last_response.consequence.status == expected_final_qiki_status
            ),
            timeout_s=8.0,
            step_s=0.1,
            label="confirmed procedure consequence",
        )
        await _wait_until(
            lambda: (
                isinstance(app._telemetry.get("sim_state"), dict)
                and str((app._telemetry.get("sim_state") or {}).get("fsm_state") or "").strip().upper() == "RUNNING"
                and bool((app._telemetry.get("sim_state") or {}).get("paused")) is False
                and abs(float((app._telemetry.get("sim_state") or {}).get("speed") or 0.0) - expected_speed) < 1e-6
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="sim_state running after procedure",
        )
        await pilot.pause()

        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("status") or "").strip().lower()
                == "confirmed"
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="confirmed observation objective closure",
        )
        await pilot.pause()
        objective = dict(app._active_observation_objective or {})
        assert objective.get("kind") == "observation_objective_update"
        assert objective.get("status") == "confirmed"
        assert objective.get("reason_code") == "OBJECTIVE_CONFIRMED"
        assert objective.get("route_role") == expected_route_role
        pre_review_qiki_status = app._qiki_last_response.consequence.status
        if observation_style == "slow":
            assert objective.get("follow_up_status") == "review_required"
            assert objective.get("follow_up_event_type") == "HIDDEN_EVENT_REVEALED"
            assert "hidden" in str(objective.get("follow_up_summary_en") or "").lower()
            assert app._qiki_last_response.legality is not None
            assert app._qiki_last_response.legality.allowed_when is not None
            assert "hidden fact" in app._qiki_last_response.legality.allowed_when.en.lower()
            await app._ack_observation_review()
            await _wait_until(
                lambda: (
                    isinstance(app._active_observation_objective, dict)
                    and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                    == "review_completed"
                ),
                timeout_s=5.0,
                step_s=0.1,
                label="review closure follow-up",
            )
            await _wait_until(
                lambda: (
                    app._qiki_last_response is not None
                    and app._qiki_last_response.consequence is not None
                    and app._qiki_last_response.consequence.status == "confirmed"
                ),
                timeout_s=5.0,
                step_s=0.1,
                label="review closure qiki consequence",
            )
            objective = dict(app._active_observation_objective or {})
            assert objective.get("reason_code") == "OBJECTIVE_REVIEW_CLOSED"
            assert objective.get("follow_up_status") == "review_completed"
            assert objective.get("follow_up_event_type") == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
            assert "choice is now open" in str(objective.get("follow_up_summary_en") or "").lower()
            assert app._qiki_last_response.legality is not None
            assert app._qiki_last_response.legality.allowed_when is not None
            assert "post-review follow-up choice" in app._qiki_last_response.legality.allowed_when.en.lower()
            await app._select_observation_recheck_hold()
            await _wait_until(
                lambda: (
                    isinstance(app._active_observation_objective, dict)
                    and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                    == "hold_for_recheck"
                ),
                timeout_s=5.0,
                step_s=0.1,
                label="post-review hold follow-up",
            )
            objective = dict(app._active_observation_objective or {})
            assert objective.get("reason_code") == "OBJECTIVE_POST_REVIEW_HOLD_SELECTED"
            assert objective.get("follow_up_status") == "hold_for_recheck"
            assert objective.get("follow_up_event_type") == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
            assert "recheck contour" in str(objective.get("follow_up_summary_en") or "").lower()
            assert app._qiki_last_response is not None
            assert app._qiki_last_response.legality is not None
            assert app._qiki_last_response.legality.allowed_when is not None
            assert "safe recheck" in app._qiki_last_response.legality.allowed_when.en.lower()
            await app._resume_observation_follow_up()
            await _wait_until(
                lambda: (
                    isinstance(app._active_observation_objective, dict)
                    and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                    == "resume_observation"
                ),
                timeout_s=5.0,
                step_s=0.1,
                label="resume observation follow-up",
            )
            objective = dict(app._active_observation_objective or {})
            assert objective.get("reason_code") == "OBJECTIVE_RESUME_OBSERVATION_SELECTED"
            assert objective.get("follow_up_status") == "resume_observation"
            assert objective.get("follow_up_event_type") == "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED"
            assert "safe observation" in str(objective.get("follow_up_allowed_when_en") or "").lower()
            resume_follow_up_status = str(objective.get("follow_up_status") or "none")
            assert app._qiki_last_response is not None
            assert app._qiki_last_response.legality is not None
            assert app._qiki_last_response.legality.allowed_when is not None
            assert "safe observation" in app._qiki_last_response.legality.allowed_when.en.lower()
            if resume_xpdr_mode:
                await app._publish_sim_command("sim.xpdr.mode", {"mode": resume_xpdr_mode})
                if not await app._wait_for_ack("sim.xpdr.mode", 2.0):
                    raise AssertionError("xpdr mode command did not receive ack before resumed observation")
                await asyncio.sleep(1.0)
                if resume_xpdr_mode == "SPOOF":
                    previous_track_id = str(objective.get("track_id") or "").strip()
                    previous_public_track_id = str(objective.get("public_track_id") or "").strip()
                    previous_track_label = str(objective.get("track_label") or "").strip()
                    changed_track, changed_label, flip_source = await asyncio.to_thread(
                        _wait_for_signature_flip_on_same_contour,
                        app,
                        target_designator=target_designator,
                        preferred_track_id=previous_track_id,
                        preferred_public_track_id=previous_public_track_id,
                        previous_track_label=previous_track_label,
                    )
                    logger.info(
                        "Signature flip precondition observed from %s: contour_track_id=%s public_track_id=%s previous_label=%s changed_label=%s",
                        flip_source,
                        previous_track_id or "missing",
                        previous_public_track_id or "missing",
                        previous_track_label or "missing",
                        changed_label or "missing",
                    )
                    if not (
                        isinstance(changed_track, dict)
                        and changed_label
                        and changed_label != previous_track_label
                    ):
                        raise AssertionError(
                            "signature_changed precondition failed: resumed contour "
                            f"track_id={previous_track_id or 'none'} kept label "
                            f"{changed_label or previous_track_label or 'none'} after sim.xpdr.mode=SPOOF"
                        )
            await app._publish_qiki_intent(f"safe observation {target_designator}")
            await _wait_until(
                lambda: app._qiki_pending_action is not None,
                timeout_s=8.0,
                step_s=0.1,
                label="resumed safe observation pending action",
            )
            await app._execute_qiki_pending_action()
            await _wait_until(
                lambda: (
                    isinstance(app._active_observation_objective, dict)
                    and str((app._active_observation_objective or {}).get("status") or "").strip().lower()
                    == "confirmed"
                    and str((app._active_observation_objective or {}).get("reason_code") or "").strip()
                    == (
                        "OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED"
                        if resume_xpdr_mode == "SPOOF"
                        else "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED"
                    )
                    and str(
                        (app._active_observation_objective or {}).get("observation_result_status") or ""
                    ).strip().lower()
                    == ("signature_changed" if resume_xpdr_mode == "SPOOF" else "reconfirmed")
                ),
                timeout_s=12.0,
                step_s=0.1,
                label="resumed safe observation continuation result",
            )
            objective = dict(app._active_observation_objective or {})
            assert objective.get("route_role") == "deviation"
            assert str(objective.get("request_id") or "").strip() == expected_request_id
            assert not objective.get("follow_up_status")
            continued_objective_id = str(objective.get("objective_id") or "none")
            continued_route_role = str(objective.get("route_role") or "none")
            continuation_result_status = str(objective.get("observation_result_status") or "none")
            assert app._qiki_last_response is not None
            assert app._qiki_last_response.consequence is not None
            if resume_xpdr_mode == "SPOOF":
                assert "signature changed" in app._qiki_last_response.consequence.summary.en.lower()
                assert str(objective.get("track_label") or "").strip().upper().startswith("SPOOF-")
            else:
                assert "reconfirmed" in app._qiki_last_response.consequence.summary.en.lower()
        else:
            assert not objective.get("follow_up_status")

        print("OK: orion_v_qiki_observation_objective_seed_smoke")
        print(f"OBSERVATION_STYLE={observation_style}")
        print(f"ROUTE_ROLE={objective.get('route_role')}")
        print(f"OBJECTIVE_ID={objective.get('objective_id')}")
        print(f"OBJECTIVE_TARGET={objective.get('target_designator')}")
        print(f"OBJECTIVE_KIND={objective.get('kind')}")
        print(f"OBJECTIVE_STATUS={objective.get('status')}")
        print(f"TRACK_ID={objective.get('track_id')}")
        print(f"TRACK_RANGE_M={objective.get('track_range_m')}")
        print(f"TRACK_QUALITY={objective.get('track_quality')}")
        print(f"OBJECTIVE_PROCEDURE={objective.get('procedure_name')}")
        print(f"INITIAL_TARGET_SOURCE={seed_source}")
        if observation_style == "slow":
            print("OBJECTIVE_FOLLOW_UP=review_required")
            print("REVIEW_ACTION=review_confirm")
            print("POST_REVIEW_CHOICE=hold_for_recheck")
            print("RESUME_ACTION=resume_observation")
            print("OBJECTIVE_FOLLOW_UP_AFTER_REVIEW=review_completed")
            print("OBJECTIVE_FOLLOW_UP_AFTER_CHOICE=hold_for_recheck")
            print(f"OBJECTIVE_FOLLOW_UP_AFTER_RESUME={resume_follow_up_status}")
            print("NEXT_ALLOWED_STEP=safe observation")
            if resume_xpdr_mode:
                print(f"RESUME_XPDR_MODE={resume_xpdr_mode}")
            print(f"CONTINUATION_RESULT={continuation_result_status}")
            print(f"CONTINUED_TARGET={target_designator}")
            print(f"CONTINUED_OBJECTIVE_ID={continued_objective_id}")
            print(f"CONTINUED_ROUTE_ROLE={continued_route_role}")
            print(f"PRE_REVIEW_QIKI_STATUS={pre_review_qiki_status}")
        else:
            print(f"OBJECTIVE_FOLLOW_UP={objective.get('follow_up_status') or 'none'}")
        if observation_style == "slow":
            hidden_line = next(
                (
                    line
                    for line in app._build_objective_timeline_lines(app._events_store)
                    if "HIDDEN_EVENT_REVEALED" in line
                ),
                None,
            )
            if hidden_line is None:
                hidden_payload = next(
                    (
                        event.get("data")
                        for event in reversed(app._events_store.last(80))
                        if isinstance(event, dict)
                        and isinstance(event.get("data"), dict)
                        and str(event["data"].get("event_type") or "").strip() == "HIDDEN_EVENT_REVEALED"
                    ),
                    None,
                )
                if isinstance(hidden_payload, dict):
                    hidden_line = (
                        "audit | HIDDEN_EVENT_REVEALED | "
                        f"{str(hidden_payload.get('message') or '').strip()}"
                    )
            assert hidden_line is not None
            print(f"HIDDEN_EVENT_LINE={hidden_line}")
        print(f"FINAL_QIKI_STATUS={app._qiki_last_response.consequence.status}")
        print(f"SIM_STATE={dict(app._telemetry.get('sim_state') or {})}")


if __name__ == "__main__":
    asyncio.run(_main())
