from __future__ import annotations

from pathlib import Path

import pytest

from qiki.services.q_core_agent.core.radar_policy_loader import (
    AdaptivePolicyConfig,
    build_effective_policy,
    load_effective_render_policy,
    validate_policy_schema,
)
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPolicy


def _minimal_policy_doc() -> dict:
    return {
        "schema_version": 1,
        "defaults": {
            "lod_vector_zoom": 1.2,
            "lod_label_zoom": 1.5,
            "lod_detail_zoom": 2.0,
            "clutter_targets_max": 30,
            "frame_budget_ms": 80.0,
            "trail_len": 20,
            "bitmap_scales": [1.0, 0.75, 0.5, 0.35],
            "degrade_cooldown_ms": 800,
            "recovery_confirm_frames": 6,
            "degrade_confirm_frames": 2,
            "manual_clutter_lock": False,
        },
        "profiles": {
            "navigation": {"clutter_targets_max": 24},
            "docking": {"frame_budget_ms": 95.0, "trail_len": 30},
            "combat": {"frame_budget_ms": 60.0, "degrade_confirm_frames": 1},
        },
        "adaptive": {
            "enabled": True,
            "degrade_confirm_frames": 3,
            "recovery_confirm_frames": 5,
            "cooldown_ms": 1200,
            "max_level": 2,
        },
    }


def test_validate_policy_schema_rejects_invalid_schema_version() -> None:
    doc = _minimal_policy_doc()
    doc["schema_version"] = 2
    errors = validate_policy_schema(doc)
    assert any("schema_version" in item for item in errors)


def test_validate_policy_schema_rejects_empty_bitmap_scales() -> None:
    doc = _minimal_policy_doc()
    doc["defaults"]["bitmap_scales"] = []
    errors = validate_policy_schema(doc)
    assert any("bitmap_scales" in item for item in errors)


def test_build_effective_policy_respects_defaults_profile_env_order() -> None:
    doc = _minimal_policy_doc()
    env = {
        "RADAR_CLUTTER_TARGETS_MAX": "77",
        "RADAR_FRAME_BUDGET_MS": "55.5",
    }
    policy, adaptive = build_effective_policy("navigation", env, doc)
    assert isinstance(policy, RadarRenderPolicy)
    assert isinstance(adaptive, AdaptivePolicyConfig)
    assert policy.clutter_targets_max == 77
    assert policy.frame_budget_ms == 55.5


def test_load_effective_render_policy_strict_mode_fails_for_broken_yaml(tmp_path: Path) -> None:
    broken = tmp_path / "broken_policy.yaml"
    broken.write_text("schema_version: 1\nprofiles: {}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Failed to load radar policy v3"):
        load_effective_render_policy(yaml_path=broken, strict=True, env={})


def test_load_effective_render_policy_non_strict_warns_and_falls_back(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken = tmp_path / "broken_policy.yaml"
    broken.write_text("schema_version: 99\n", encoding="utf-8")
    caplog.set_level("WARNING")
    policy, adaptive = load_effective_render_policy(yaml_path=broken, strict=False, env={})
    assert policy == RadarRenderPolicy.from_env()
    assert adaptive == AdaptivePolicyConfig()
    assert any("fallback to env/default policy" in rec.message for rec in caplog.records)
