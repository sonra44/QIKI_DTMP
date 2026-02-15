"""Loader for radar render policy v3 (YAML profiles + env overrides)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping

import yaml

from .radar_render_policy import RadarRenderPolicy
from .runtime_contracts import resolve_strict_mode

LOGGER = logging.getLogger(__name__)

DEFAULT_POLICY_RESOURCE_PACKAGE = "qiki.resources.radar"
DEFAULT_POLICY_RESOURCE_NAME = "policy_v3.yaml"
DEFAULT_PROFILE = "navigation"
SUPPORTED_PROFILES = ("navigation", "docking", "combat")

_ENV_TO_FIELD = {
    "RADAR_LOD_VECTOR_ZOOM": "lod_vector_zoom",
    "RADAR_LOD_LABEL_ZOOM": "lod_label_zoom",
    "RADAR_LOD_DETAIL_ZOOM": "lod_detail_zoom",
    "RADAR_CLUTTER_TARGETS_MAX": "clutter_targets_max",
    "RADAR_FRAME_BUDGET_MS": "frame_budget_ms",
    "RADAR_TRAIL_LEN": "trail_len",
    "RADAR_BITMAP_SCALES": "bitmap_scales",
    "RADAR_DEGRADE_COOLDOWN_MS": "degrade_cooldown_ms",
    "RADAR_RECOVERY_CONFIRM_FRAMES": "recovery_confirm_frames",
    "RADAR_DEGRADE_CONFIRM_FRAMES": "degrade_confirm_frames",
    "RADAR_MANUAL_CLUTTER_LOCK": "manual_clutter_lock",
}
_REQUIRED_POLICY_KEYS = set(_ENV_TO_FIELD.values())


@dataclass(frozen=True)
class AdaptivePolicyConfig:
    enabled: bool = True
    ema_alpha_frame_ms: float = 0.35
    ema_alpha_targets: float = 0.25
    high_frame_ratio: float = 1.2
    low_frame_ratio: float = 0.8
    overload_target_ratio: float = 1.15
    underload_target_ratio: float = 0.75
    degrade_confirm_frames: int = 3
    recovery_confirm_frames: int = 5
    cooldown_ms: int = 1200
    max_level: int = 2
    clutter_reduction_per_level: float = 0.2
    lod_label_zoom_delta_per_level: float = 0.2
    lod_detail_zoom_delta_per_level: float = 0.15


@dataclass(frozen=True)
class RadarPolicyLoadResult:
    render_policy: RadarRenderPolicy
    adaptive_policy: AdaptivePolicyConfig
    selected_profile: str
    policy_source: str
    warning_reason: str = ""


def _to_float(value: object, *, minimum: float | None = None) -> float:
    converted = float(value)
    if minimum is not None and converted < minimum:
        raise ValueError(f"value must be >= {minimum}")
    return converted


def _to_int(value: object, *, minimum: int | None = None) -> int:
    converted = int(value)
    if minimum is not None and converted < minimum:
        raise ValueError(f"value must be >= {minimum}")
    return converted


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_bitmap_scales(value: object) -> tuple[float, ...]:
    if isinstance(value, str):
        scales = RadarRenderPolicy._parse_bitmap_scales(value)
        if not scales:
            raise ValueError("bitmap_scales must not be empty")
        return scales
    if not isinstance(value, list):
        raise ValueError("bitmap_scales must be a list or comma-separated string")
    parsed: list[float] = []
    for item in value:
        numeric = _to_float(item)
        if numeric <= 0.0:
            continue
        parsed.append(numeric)
    if not parsed:
        raise ValueError("bitmap_scales must contain at least one value > 0")
    return tuple(parsed)


def _policy_from_mapping(raw: Mapping[str, object], *, path_prefix: str = "policy") -> RadarRenderPolicy:
    def _float_field(name: str, minimum: float | None = None) -> float:
        value = raw.get(name)
        try:
            return _to_float(value, minimum=minimum)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{path_prefix}.{name}={value!r}: {exc}") from exc

    def _int_field(name: str, minimum: int | None = None) -> int:
        value = raw.get(name)
        try:
            return _to_int(value, minimum=minimum)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{path_prefix}.{name}={value!r}: {exc}") from exc

    def _bool_field(name: str) -> bool:
        value = raw.get(name)
        try:
            return _to_bool(value)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{path_prefix}.{name}={value!r}: {exc}") from exc

    try:
        bitmap_scales = _normalize_bitmap_scales(raw["bitmap_scales"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path_prefix}.bitmap_scales={raw.get('bitmap_scales')!r}: {exc}") from exc
    return RadarRenderPolicy(
        lod_vector_zoom=_float_field("lod_vector_zoom", minimum=0.0),
        lod_label_zoom=_float_field("lod_label_zoom", minimum=0.0),
        lod_detail_zoom=_float_field("lod_detail_zoom", minimum=0.0),
        clutter_targets_max=max(1, _int_field("clutter_targets_max", minimum=1)),
        frame_budget_ms=max(1.0, _float_field("frame_budget_ms", minimum=0.001)),
        trail_len=max(1, _int_field("trail_len", minimum=1)),
        bitmap_scales=bitmap_scales,
        degrade_cooldown_ms=max(0, _int_field("degrade_cooldown_ms", minimum=0)),
        recovery_confirm_frames=max(1, _int_field("recovery_confirm_frames", minimum=1)),
        degrade_confirm_frames=max(1, _int_field("degrade_confirm_frames", minimum=1)),
        manual_clutter_lock=_bool_field("manual_clutter_lock"),
    )


def _adaptive_from_mapping(raw: Mapping[str, object], *, path_prefix: str = "adaptive") -> AdaptivePolicyConfig:
    try:
        return AdaptivePolicyConfig(
            enabled=_to_bool(raw.get("enabled", True)),
            ema_alpha_frame_ms=_to_float(raw.get("ema_alpha_frame_ms", 0.35), minimum=0.0),
            ema_alpha_targets=_to_float(raw.get("ema_alpha_targets", 0.25), minimum=0.0),
            high_frame_ratio=_to_float(raw.get("high_frame_ratio", 1.2), minimum=0.001),
            low_frame_ratio=_to_float(raw.get("low_frame_ratio", 0.8), minimum=0.0),
            overload_target_ratio=_to_float(raw.get("overload_target_ratio", 1.15), minimum=0.001),
            underload_target_ratio=_to_float(raw.get("underload_target_ratio", 0.75), minimum=0.0),
            degrade_confirm_frames=max(1, _to_int(raw.get("degrade_confirm_frames", 3), minimum=1)),
            recovery_confirm_frames=max(1, _to_int(raw.get("recovery_confirm_frames", 5), minimum=1)),
            cooldown_ms=max(0, _to_int(raw.get("cooldown_ms", 1200), minimum=0)),
            max_level=max(0, _to_int(raw.get("max_level", 2), minimum=0)),
            clutter_reduction_per_level=_to_float(raw.get("clutter_reduction_per_level", 0.2), minimum=0.0),
            lod_label_zoom_delta_per_level=_to_float(raw.get("lod_label_zoom_delta_per_level", 0.2), minimum=0.0),
            lod_detail_zoom_delta_per_level=_to_float(raw.get("lod_detail_zoom_delta_per_level", 0.15), minimum=0.0),
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path_prefix}: {exc}") from exc


def load_policy_yaml(path: str | Path | None = None) -> dict:
    if path is not None:
        with Path(path).expanduser().resolve().open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    else:
        resource = resources.files(DEFAULT_POLICY_RESOURCE_PACKAGE).joinpath(DEFAULT_POLICY_RESOURCE_NAME)
        if not resource.is_file():  # type: ignore[attr-defined]
            raise FileNotFoundError(
                f"Radar policy resource not found: {DEFAULT_POLICY_RESOURCE_PACKAGE}:{DEFAULT_POLICY_RESOURCE_NAME}"
            )
        with resource.open("r", encoding="utf-8") as handle:  # type: ignore[attr-defined]
            loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("radar policy yaml must be a mapping")
    return loaded


def validate_policy_schema(doc: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    schema_version = doc.get("schema_version")
    if schema_version != 1:
        errors.append("schema_version must be 1")

    defaults = doc.get("defaults")
    if not isinstance(defaults, dict):
        errors.append("defaults must be a mapping")
    else:
        missing = sorted(_REQUIRED_POLICY_KEYS - set(defaults.keys()))
        if missing:
            errors.append(f"defaults missing required keys: {', '.join(missing)}")
        else:
            try:
                _policy_from_mapping(defaults, path_prefix="defaults")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

    profiles = doc.get("profiles")
    if not isinstance(profiles, dict):
        errors.append("profiles must be a mapping")
    else:
        for profile_name in SUPPORTED_PROFILES:
            profile_doc = profiles.get(profile_name)
            if profile_doc is None:
                errors.append(f"profiles.{profile_name} is required")
                continue
            if not isinstance(profile_doc, dict):
                errors.append(f"profiles.{profile_name} must be a mapping")
                continue
            merged = dict(defaults or {})
            merged.update(profile_doc)
            try:
                _policy_from_mapping(merged, path_prefix=f"profiles.{profile_name}")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

    adaptive = doc.get("adaptive")
    if adaptive is not None:
        if not isinstance(adaptive, dict):
            errors.append("adaptive must be a mapping")
        else:
            try:
                _adaptive_from_mapping(adaptive, path_prefix="adaptive")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
    return errors


def _env_policy_overrides(env: Mapping[str, str]) -> dict[str, object]:
    overrides: dict[str, object] = {}
    if "RADAR_LOD_VECTOR_ZOOM" in env:
        try:
            overrides["lod_vector_zoom"] = float(env["RADAR_LOD_VECTOR_ZOOM"])
        except Exception:
            pass
    if "RADAR_LOD_LABEL_ZOOM" in env:
        try:
            overrides["lod_label_zoom"] = float(env["RADAR_LOD_LABEL_ZOOM"])
        except Exception:
            pass
    if "RADAR_LOD_DETAIL_ZOOM" in env:
        try:
            overrides["lod_detail_zoom"] = float(env["RADAR_LOD_DETAIL_ZOOM"])
        except Exception:
            pass
    if "RADAR_CLUTTER_TARGETS_MAX" in env:
        try:
            overrides["clutter_targets_max"] = max(1, int(env["RADAR_CLUTTER_TARGETS_MAX"]))
        except Exception:
            pass
    if "RADAR_FRAME_BUDGET_MS" in env:
        try:
            overrides["frame_budget_ms"] = max(1.0, float(env["RADAR_FRAME_BUDGET_MS"]))
        except Exception:
            pass
    if "RADAR_TRAIL_LEN" in env:
        try:
            overrides["trail_len"] = max(1, int(env["RADAR_TRAIL_LEN"]))
        except Exception:
            pass
    if "RADAR_BITMAP_SCALES" in env:
        try:
            overrides["bitmap_scales"] = RadarRenderPolicy._parse_bitmap_scales(env["RADAR_BITMAP_SCALES"])
        except Exception:
            pass
    if "RADAR_DEGRADE_COOLDOWN_MS" in env:
        try:
            overrides["degrade_cooldown_ms"] = max(0, int(env["RADAR_DEGRADE_COOLDOWN_MS"]))
        except Exception:
            pass
    if "RADAR_RECOVERY_CONFIRM_FRAMES" in env:
        try:
            overrides["recovery_confirm_frames"] = max(1, int(env["RADAR_RECOVERY_CONFIRM_FRAMES"]))
        except Exception:
            pass
    if "RADAR_DEGRADE_CONFIRM_FRAMES" in env:
        try:
            overrides["degrade_confirm_frames"] = max(1, int(env["RADAR_DEGRADE_CONFIRM_FRAMES"]))
        except Exception:
            pass
    if "RADAR_MANUAL_CLUTTER_LOCK" in env:
        overrides["manual_clutter_lock"] = env["RADAR_MANUAL_CLUTTER_LOCK"].strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    return overrides


def build_effective_policy(
    profile: str,
    env: Mapping[str, str],
    yaml_doc: Mapping[str, object],
) -> tuple[RadarRenderPolicy, AdaptivePolicyConfig]:
    defaults = yaml_doc.get("defaults", {})
    profiles = yaml_doc.get("profiles", {})
    profile_doc = profiles.get(profile)
    if not isinstance(profile_doc, dict):
        raise ValueError(f"unknown radar policy profile: {profile}")

    merged: dict[str, object] = {}
    if isinstance(defaults, dict):
        merged.update(defaults)
    merged.update(profile_doc)
    merged.update(_env_policy_overrides(env))
    render_policy = _policy_from_mapping(merged, path_prefix=f"profiles.{profile}")

    adaptive_doc = yaml_doc.get("adaptive", {})
    adaptive = _adaptive_from_mapping(
        adaptive_doc if isinstance(adaptive_doc, dict) else {},
        path_prefix="adaptive",
    )
    return render_policy, adaptive


def _fallback_policy_source(env: Mapping[str, str]) -> str:
    for key in _ENV_TO_FIELD:
        if key in env:
            return "env"
    return "default"


def load_effective_render_policy_result(
    *,
    profile: str | None = None,
    env: Mapping[str, str] | None = None,
    yaml_path: str | Path | None = None,
    strict: bool | None = None,
) -> RadarPolicyLoadResult:
    active_env = env or os.environ
    selected_profile = (profile or active_env.get("RADAR_POLICY_PROFILE", DEFAULT_PROFILE)).strip().lower() or DEFAULT_PROFILE
    strict_mode = (
        resolve_strict_mode(active_env, legacy_keys=("RADAR_POLICY_STRICT",), default=False)
        if strict is None
        else strict
    )
    resolved_path = yaml_path if yaml_path is not None else active_env.get("RADAR_POLICY_YAML")
    if resolved_path is not None and str(resolved_path).strip().lower() in {"", "0", "off", "none", "disabled"}:
        resolved_path = None

    try:
        yaml_doc = load_policy_yaml(resolved_path)
        errors = validate_policy_schema(yaml_doc)
        if errors:
            raise ValueError("; ".join(errors))
        if selected_profile not in SUPPORTED_PROFILES:
            raise ValueError(f"unsupported RADAR_POLICY_PROFILE={selected_profile!r}")
        render_policy, adaptive = build_effective_policy(selected_profile, active_env, yaml_doc)
        return RadarPolicyLoadResult(
            render_policy=render_policy,
            adaptive_policy=adaptive,
            selected_profile=selected_profile,
            policy_source="yaml",
        )
    except Exception as exc:  # noqa: BLE001
        if strict_mode:
            raise RuntimeError(f"Failed to load radar policy v3: {exc}") from exc
        warning = f"POLICY_FALLBACK: radar policy v3 unavailable, fallback to env/default policy: {exc}"
        LOGGER.warning(warning)
        return RadarPolicyLoadResult(
            render_policy=RadarRenderPolicy.from_env(),
            adaptive_policy=AdaptivePolicyConfig(),
            selected_profile=selected_profile if selected_profile in SUPPORTED_PROFILES else DEFAULT_PROFILE,
            policy_source=_fallback_policy_source(active_env),
            warning_reason=warning,
        )


def load_effective_render_policy(
    *,
    profile: str | None = None,
    env: Mapping[str, str] | None = None,
    yaml_path: str | Path | None = None,
    strict: bool | None = None,
) -> tuple[RadarRenderPolicy, AdaptivePolicyConfig]:
    result = load_effective_render_policy_result(
        profile=profile,
        env=env,
        yaml_path=yaml_path,
        strict=strict,
    )
    return result.render_policy, result.adaptive_policy
