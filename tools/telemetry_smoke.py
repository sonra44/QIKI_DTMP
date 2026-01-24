from __future__ import annotations

import asyncio
import json
import os
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Any


async def main() -> int:
    parser = ArgumentParser(description="QIKI telemetry smoke / audit")
    parser.add_argument(
        "--audit-dictionary",
        action="store_true",
        help="Compare one real qiki.telemetry payload against TELEMETRY_DICTIONARY.yaml",
    )
    parser.add_argument(
        "--dictionary-path",
        default="docs/design/operator_console/TELEMETRY_DICTIONARY.yaml",
        help="Path to TELEMETRY_DICTIONARY.yaml (repo-relative by default)",
    )
    parser.add_argument(
        "--subsystems",
        default="power,thermal,sensors,propulsion,comms,system,docking",
        help="Comma-separated subsystems to audit (default: power,thermal,sensors,propulsion,comms,system,docking)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 1) if dictionary has required paths missing in payload",
    )
    args = parser.parse_args()

    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", "qiki.telemetry")
    timeout_s = float(os.getenv("TELEMETRY_SMOKE_TIMEOUT_SEC", "3.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=2)
    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            got.set_result(json.loads(msg.data.decode("utf-8")))
        except Exception:
            got.set_result({"raw": msg.data.decode("utf-8", errors="replace")})

    sub = await nc.subscribe(subject, cb=handler)
    try:
        payload = await asyncio.wait_for(got, timeout=timeout_s)
        pos = payload.get("position") if isinstance(payload, dict) else None
        if not isinstance(pos, dict) or not {"x", "y", "z"} <= set(pos.keys()):
            print(f"BAD: telemetry missing 3D position on {subject}: {payload}")
            return 1
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            print(f"BAD: telemetry schema_version != 1 on {subject}: {payload}")
            return 1
        if "ts_unix_ms" not in payload:
            print(f"BAD: telemetry missing ts_unix_ms on {subject}: {payload}")
            return 1
        power = payload.get("power") if isinstance(payload, dict) else None
        if not isinstance(power, dict) or not {
            "soc_pct",
            "power_in_w",
            "power_out_w",
            "bus_v",
            "bus_a",
        } <= set(power.keys()):
            print(f"BAD: telemetry missing power/EPS fields on {subject}: {payload}")
            return 1
        attitude = payload.get("attitude") if isinstance(payload, dict) else None
        if not isinstance(attitude, dict) or not {
            "roll_rad",
            "pitch_rad",
            "yaw_rad",
        } <= set(attitude.keys()):
            print(f"BAD: telemetry missing attitude fields on {subject}: {payload}")
            return 1
        thermal = payload.get("thermal") if isinstance(payload, dict) else None
        if not isinstance(thermal, dict):
            print(f"BAD: telemetry missing thermal block on {subject}: {payload}")
            return 1
        nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
        if not isinstance(nodes, list) or not nodes:
            print(f"BAD: telemetry missing thermal nodes on {subject}: {payload}")
            return 1
        if args.audit_dictionary:
            audit_rc = _audit_dictionary(
                payload,
                dictionary_path=args.dictionary_path,
                subsystems_csv=args.subsystems,
                strict=bool(args.strict),
            )
            if audit_rc != 0:
                return audit_rc

        if args.audit_dictionary:
            print(f"OK: received telemetry on {subject}")
        else:
            print(f"OK: received telemetry on {subject}: {payload}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no telemetry on {subject} within {timeout_s}s")
        return 1
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        await nc.drain()
        await nc.close()


def _repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[1]
    except Exception:
        return Path.cwd()


def _canonicalize_path(path: str) -> str:
    # Convert selectors like [id=core] or [index=3] to wildcard form.
    return re.sub(r"\[[a-zA-Z_]+=[^\]]+\]", "[*]", str(path))


def _walk_paths(obj: Any, prefix: str, *, out: set[str], empty_lists: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or not k:
                continue
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            _walk_paths(v, p, out=out, empty_lists=empty_lists)
        return

    if isinstance(obj, list):
        p_wild = f"{prefix}[*]" if prefix else "[*]"
        out.add(p_wild)
        if not obj:
            empty_lists.add(p_wild)
            return
        for item in obj:
            _walk_paths(item, p_wild, out=out, empty_lists=empty_lists)
        return


def _extract_subsystem_block(payload: dict[str, Any], subsystem: str) -> Any:
    mapping = {
        "sensors": "sensor_plane",
    }
    if subsystem == "system":
        # System is a mixed selection: sim_state + hardware_profile_hash.
        return {
            "sim_state": payload.get("sim_state"),
            "hardware_profile_hash": payload.get("hardware_profile_hash"),
        }
    key = mapping.get(subsystem, subsystem)
    if subsystem == "power":
        # Power is split between top-level `battery` and the nested `power` block.
        return {"battery": payload.get("battery"), "power": payload.get("power")}
    return payload.get(key)


def _audit_dictionary(payload: dict[str, Any], *, dictionary_path: str, subsystems_csv: str, strict: bool) -> int:
    try:
        import yaml
    except Exception as exc:
        print(f"AUDIT: yaml import failed: {exc}")
        return 2

    root = _repo_root()
    dict_path = Path(dictionary_path)
    if not dict_path.is_absolute():
        dict_path = root / dict_path

    try:
        d = yaml.safe_load(dict_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"AUDIT: failed to read dictionary {dict_path}: {exc}")
        return 2
    if not isinstance(d, dict):
        print(f"AUDIT: dictionary not a mapping: {dict_path}")
        return 2
    subs = d.get("subsystems")
    if not isinstance(subs, dict):
        print(f"AUDIT: dictionary missing subsystems: {dict_path}")
        return 2

    requested = [s.strip() for s in str(subsystems_csv).split(",") if s.strip()]
    if not requested:
        print("AUDIT: no subsystems requested")
        return 2

    dict_paths: set[str] = set()
    state_dependent: set[str] = set()
    for sid in requested:
        block = subs.get(sid)
        if not isinstance(block, dict):
            continue
        fields = block.get("fields")
        if not isinstance(fields, list):
            continue
        for f in fields:
            if not isinstance(f, dict):
                continue
            p = f.get("path")
            if isinstance(p, str) and p.strip():
                dict_paths.add(p.strip())
                if str(f.get("presence") or "").strip().lower() == "state-dependent":
                    state_dependent.add(p.strip())
            dims = f.get("dimensions")
            if isinstance(dims, dict):
                dk = dims.get("key")
                if isinstance(dk, str) and dk.strip():
                    dict_paths.add(dk.strip())
            rel = f.get("related")
            if isinstance(rel, list):
                for r in rel:
                    if isinstance(r, str) and r.strip():
                        dict_paths.add(r.strip())

    payload_paths: set[str] = set()
    empty_lists: set[str] = set()
    for sid in requested:
        subtree = _extract_subsystem_block(payload, sid)
        if subtree is None:
            continue
        base_key = "sensor_plane" if sid == "sensors" else sid
        if sid in {"system", "power"}:
            _walk_paths(subtree, "", out=payload_paths, empty_lists=empty_lists)
        else:
            _walk_paths(subtree, base_key, out=payload_paths, empty_lists=empty_lists)

    payload_paths = {_canonicalize_path(p) for p in payload_paths}

    def is_blocked_by_empty_list(path: str) -> bool:
        for empty in empty_lists:
            if path.startswith(empty + "."):
                return True
        return False

    missing_in_payload = sorted(
        [
            p
            for p in dict_paths
            if (p not in payload_paths) and (p not in state_dependent) and (not is_blocked_by_empty_list(p))
        ]
    )
    dict_prefixes: set[str] = set()
    for p in dict_paths:
        parts = [x for x in p.split(".") if x]
        for i in range(1, len(parts)):
            dict_prefixes.add(".".join(parts[:i]))

    missing_in_dictionary = sorted(
        [
            p
            for p in payload_paths
            if p not in dict_paths
            and p not in dict_prefixes
            and not p.endswith("[*]")
            and not ((p + "[*]") in dict_paths or (p + "[*]") in dict_prefixes)
        ]
    )

    # Print a compact audit report.
    print(f"AUDIT: dictionary={dict_path}")
    print(f"AUDIT: subsystems={','.join(requested)}")
    print(f"AUDIT: payload_paths={len(payload_paths)} dict_paths={len(dict_paths)}")
    if empty_lists:
        print(f"AUDIT: empty_lists={sorted(empty_lists)}")

    if missing_in_payload:
        print(f"AUDIT: MISSING_IN_PAYLOAD ({len(missing_in_payload)}):")
        for p in missing_in_payload[:50]:
            print(f"- {p}")

    if missing_in_dictionary:
        print(f"AUDIT: NOT_IN_DICTIONARY ({len(missing_in_dictionary)}):")
        for p in missing_in_dictionary[:50]:
            print(f"- {p}")

    if missing_in_payload and strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
