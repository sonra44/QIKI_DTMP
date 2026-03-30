from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from qiki.services.operator_console.orion_v.app import OrionVApp
from tools.orion_v_target_seed_sources import pick_public_target_from_tracks
from tools.orion_v_qiki_observation_objective_seed_smoke import _probe_qiki_roundtrip, _wait_until


logging.basicConfig(level=logging.INFO)


def _pick_live_target_designator_from_orion(
    app: OrionVApp,
    *,
    require_non_spoof: bool = False,
) -> tuple[str, dict[str, Any]]:
    return pick_public_target_from_tracks(
        app._latest_radar_tracks.values(),
        require_non_spoof=require_non_spoof,
    )


def _snapshot_track_entry(track: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(track, dict):
        return None
    return {
        "track_id": track.get("track_id"),
        "track_label": track.get("transponder_id") or track.get("id") or track.get("callsign"),
        "status": track.get("status"),
        "range_m": track.get("range_m"),
        "quality": track.get("quality"),
        "_orion_source_timestamp_unix_s": track.get("_orion_source_timestamp_unix_s"),
        "_orion_received_at_unix_s": track.get("_orion_received_at_unix_s"),
        "timestamp": track.get("timestamp"),
        "ts_unix_ms": track.get("ts_unix_ms"),
        "ts_unix_s": track.get("ts_unix_s"),
    }


async def _main() -> None:
    os.environ.setdefault("RADAR_TRACKS_DURABLE", "")
    os.environ.setdefault("QIKI_OBSERVATION_STYLE", "slow")
    os.environ.setdefault("QIKI_RESUME_XPDR_MODE", "SPOOF")
    os.environ.setdefault("QIKI_INITIAL_XPDR_MODE", "ON")

    app = OrionVApp()
    captured: dict[str, Any] = {}
    original_build = app._build_resume_observation_result

    def _wrapped_build_resume_observation_result(
        objective: dict[str, Any] | None,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, str] | None:
        previous_track_id = str((objective or {}).get("track_id") or "").strip() if isinstance(objective, dict) else ""
        live_track = app._latest_radar_tracks.get(previous_track_id)
        captured["precomparison"] = {
            "objective": {
                "objective_id": (objective or {}).get("objective_id") if isinstance(objective, dict) else None,
                "request_id": (objective or {}).get("request_id") if isinstance(objective, dict) else None,
                "target_designator": (objective or {}).get("target_designator") if isinstance(objective, dict) else None,
                "follow_up_status": (objective or {}).get("follow_up_status") if isinstance(objective, dict) else None,
                "previous_track_id": (objective or {}).get("track_id") if isinstance(objective, dict) else None,
                "previous_track_label": (objective or {}).get("track_label") if isinstance(objective, dict) else None,
            },
            "parameters_entering_build": {
                "observation_track_id": (parameters or {}).get("observation_track_id") if isinstance(parameters, dict) else None,
                "observation_track_label": (parameters or {}).get("observation_track_label") if isinstance(parameters, dict) else None,
                "observation_track_range_m": (parameters or {}).get("observation_track_range_m") if isinstance(parameters, dict) else None,
                "observation_track_quality": (parameters or {}).get("observation_track_quality") if isinstance(parameters, dict) else None,
                "source": (parameters or {}).get("source") if isinstance(parameters, dict) else None,
                "label_source": (parameters or {}).get("label_source") if isinstance(parameters, dict) else None,
                "source_timestamp_unix_s": (parameters or {}).get("source_timestamp_unix_s") if isinstance(parameters, dict) else None,
                "freshness_s": (parameters or {}).get("freshness_s") if isinstance(parameters, dict) else None,
            },
            "live_cache_entry_for_previous_track": _snapshot_track_entry(live_track),
        }
        result = original_build(objective, parameters=parameters)
        captured["precomparison"]["result"] = result
        print("PRECOMPARISON_CAPTURE=" + json.dumps(captured["precomparison"], ensure_ascii=True, sort_keys=True))
        return result

    app._build_resume_observation_result = _wrapped_build_resume_observation_result

    async with app.run_test(size=(160, 48)):
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
        await _wait_until(
            lambda: bool(app._latest_radar_tracks),
            timeout_s=10.0,
            step_s=0.1,
            label="ORION live radar cache",
        )
        await _probe_qiki_roundtrip(app)

        initial_xpdr_mode = str(os.getenv("QIKI_INITIAL_XPDR_MODE") or "").strip().upper()
        if initial_xpdr_mode:
            await app._publish_sim_command("sim.xpdr.mode", {"mode": initial_xpdr_mode})
            if not await app._wait_for_ack("sim.xpdr.mode", 2.0):
                raise AssertionError("initial xpdr mode command did not receive ack")
            await asyncio.sleep(1.0)

        target_designator, seed_track = _pick_live_target_designator_from_orion(app, require_non_spoof=True)
        print(
            "INITIAL_TARGET="
            + json.dumps(
                {
                    "target_designator": target_designator,
                    "orion_track": _snapshot_track_entry(seed_track),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )

        await app._publish_qiki_intent(f"slow observation {target_designator}")
        await _wait_until(
            lambda: app._qiki_last_response is not None,
            timeout_s=12.0,
            step_s=0.1,
            label="initial QIKI response",
        )
        expected_request_id = str(app._qiki_last_response.request_id)
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("request_id") or "").strip()
                == expected_request_id
                and str((app._active_observation_objective or {}).get("observation_style") or "").strip().lower()
                == "slow"
            ),
            timeout_s=12.0,
            step_s=0.1,
            label="observation objective seed",
        )
        await app._execute_qiki_pending_action()
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("status") or "").strip().lower() == "confirmed"
                and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                == "review_required"
            ),
            timeout_s=8.0,
            step_s=0.1,
            label="review_required objective",
        )

        await app._ack_observation_review()
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                == "review_completed"
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="review_completed follow-up",
        )
        await app._select_observation_recheck_hold()
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                == "hold_for_recheck"
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="hold_for_recheck follow-up",
        )
        await app._resume_observation_follow_up()
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("follow_up_status") or "").strip().lower()
                == "resume_observation"
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="resume_observation follow-up",
        )

        resumed_objective = dict(app._active_observation_objective or {})
        print(
            "RESUMED_OBJECTIVE_BEFORE_SPOOF="
            + json.dumps(
                {
                    "objective_id": resumed_objective.get("objective_id"),
                    "request_id": resumed_objective.get("request_id"),
                    "target_designator": resumed_objective.get("target_designator"),
                    "track_id": resumed_objective.get("track_id"),
                    "track_label": resumed_objective.get("track_label"),
                    "follow_up_status": resumed_objective.get("follow_up_status"),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )

        await app._publish_sim_command("sim.xpdr.mode", {"mode": "SPOOF"})
        if not await app._wait_for_ack("sim.xpdr.mode", 2.0):
            raise AssertionError("xpdr mode command did not receive ack before resumed observation")
        await asyncio.sleep(1.0)

        previous_track_id = str(resumed_objective.get("track_id") or "").strip()
        live_before_resume = app._latest_radar_tracks.get(previous_track_id)
        print(
            "ORION_CACHE_BEFORE_RESUMED_EXEC="
            + json.dumps(
                {
                    "previous_track_id": previous_track_id or None,
                    "live_entry": _snapshot_track_entry(live_before_resume),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )

        await app._publish_qiki_intent(f"safe observation {target_designator}")
        await _wait_until(
            lambda: app._qiki_pending_action is not None,
            timeout_s=8.0,
            step_s=0.1,
            label="resumed safe observation pending action",
        )
        print(
            "PENDING_ACTION_BEFORE_EXEC="
            + json.dumps(
                {
                    "action_kind": app._qiki_pending_action.get("action_kind"),
                    "name": app._qiki_pending_action.get("name"),
                    "parameters": app._qiki_pending_action.get("parameters"),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )

        await app._execute_qiki_pending_action()
        await _wait_until(
            lambda: "precomparison" in captured,
            timeout_s=8.0,
            step_s=0.1,
            label="precomparison capture",
        )
        await _wait_until(
            lambda: (
                isinstance(app._active_observation_objective, dict)
                and str((app._active_observation_objective or {}).get("status") or "").strip().lower() == "confirmed"
                and not str((app._active_observation_objective or {}).get("follow_up_status") or "").strip()
            ),
            timeout_s=12.0,
            step_s=0.1,
            label="resumed objective closure",
        )

        final_objective = dict(app._active_observation_objective or {})
        print(
            "FINAL_OBJECTIVE="
            + json.dumps(
                {
                    "objective_id": final_objective.get("objective_id"),
                    "request_id": final_objective.get("request_id"),
                    "reason_code": final_objective.get("reason_code"),
                    "observation_result_status": final_objective.get("observation_result_status"),
                    "track_id": final_objective.get("track_id"),
                    "track_label": final_objective.get("track_label"),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    asyncio.run(_main())
