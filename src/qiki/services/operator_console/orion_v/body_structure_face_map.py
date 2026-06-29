"""Terminal Face Map renderer for visible QIKI Body Structure telemetry.

This module is a view/read-model helper only. It renders the existing
body_structure skeleton Face Map (F00-F11) for ORION V and does not add geometry,
face normals, dynamic mount creation, PDU, thermal clearance, bayonet bridge,
capability activation, or 3D/MFD rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiki.services.q_core_agent.core.body_structure import BodyConfigSnapshot, FACE_IDS

DEFAULT_SELECTED_FACE_ID = "F06"

_FACE_ROLES: dict[str, str] = {
    "F00": "bayonet",
    "F01": "bayonet",
    "F02": "rcs",
    "F03": "rcs",
    "F04": "rcs",
    "F05": "rcs",
    "F06": "mission",
    "F07": "mission",
    "F08": "thermal",
    "F09": "thermal",
    "F10": "utility",
    "F11": "utility",
}


@dataclass(frozen=True, slots=True)
class BodyStructureFaceRow:
    face_id: str
    role: str
    occupancy: str
    module_id: str
    selected: bool = False


def face_role(face_id: str) -> str:
    """Return the skeleton/operator role for a face.

    This role map is a visible skeleton for ORION. It is not a calculated geometry
    claim and must not be treated as final Face Map canon.
    """
    return _FACE_ROLES.get(face_id, "unknown")


def normalize_selected_face_id(face_id: str | None, face_ids: tuple[str, ...] = FACE_IDS) -> str:
    if face_id in face_ids:
        return str(face_id)
    return DEFAULT_SELECTED_FACE_ID if DEFAULT_SELECTED_FACE_ID in face_ids else face_ids[0]


def next_face_id(current_face_id: str | None, face_ids: tuple[str, ...] = FACE_IDS) -> str:
    selected = normalize_selected_face_id(current_face_id, face_ids)
    index = face_ids.index(selected)
    return face_ids[(index + 1) % len(face_ids)]


def previous_face_id(current_face_id: str | None, face_ids: tuple[str, ...] = FACE_IDS) -> str:
    selected = normalize_selected_face_id(current_face_id, face_ids)
    index = face_ids.index(selected)
    return face_ids[(index - 1) % len(face_ids)]


def build_body_structure_face_rows(
    body: BodyConfigSnapshot,
    *,
    selected_face_id: str | None = None,
) -> tuple[BodyStructureFaceRow, ...]:
    selected = normalize_selected_face_id(selected_face_id, body.face_ids)
    rows: list[BodyStructureFaceRow] = []
    for face_id in body.face_ids:
        raw_occupancy = str(body.face_occupancy.get(face_id) or "unknown")
        if raw_occupancy == "free":
            occupancy = "free"
            module_id = ""
        elif raw_occupancy == "unknown":
            occupancy = "unknown"
            module_id = ""
        else:
            occupancy = "occupied"
            module_id = raw_occupancy
        rows.append(
            BodyStructureFaceRow(
                face_id=face_id,
                role=face_role(face_id),
                occupancy=occupancy,
                module_id=module_id,
                selected=face_id == selected,
            )
        )
    return tuple(rows)


def selected_face_row(rows: tuple[BodyStructureFaceRow, ...], selected_face_id: str | None) -> BodyStructureFaceRow:
    selected = normalize_selected_face_id(selected_face_id, tuple(row.face_id for row in rows))
    for row in rows:
        if row.face_id == selected:
            return row
    return rows[0]


def format_body_structure_face_map(rows: tuple[BodyStructureFaceRow, ...]) -> str:
    lines = ["Face Map"]
    for row in rows:
        marker = ">" if row.selected else " "
        if row.occupancy == "occupied":
            state = f"OCCUPIED  {row.module_id}"
        else:
            state = row.occupancy
        lines.append(f"{marker} {row.face_id:<3} {row.role:<8} {state}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backward-compatible aliases for the pre-Textual body-structure view model.
#
# The Textual dashboard renamed FaceView -> FaceRow and the formatter helpers,
# but downstream visible/interactive view-models still import the old helper
# names. Keep these aliases until those callers are migrated explicitly.
# This is UI/read-model compatibility only; it does not change runtime body state.

BodyStructureFaceView = BodyStructureFaceRow


def default_selected_face_id() -> str:
    return DEFAULT_SELECTED_FACE_ID


def build_face_views(
    body: BodyConfigSnapshot,
    *,
    selected_face_id: str | None = None,
) -> tuple[BodyStructureFaceView, ...]:
    return build_body_structure_face_rows(body, selected_face_id=selected_face_id)


def selected_face_view(
    body: BodyConfigSnapshot,
    *,
    selected_face_id: str | None = None,
) -> BodyStructureFaceView:
    rows = build_body_structure_face_rows(body, selected_face_id=selected_face_id)
    return selected_face_row(rows, selected_face_id)


def format_face_map_lines(rows: tuple[BodyStructureFaceView, ...]) -> tuple[str, ...]:
    return tuple(format_body_structure_face_map(rows).splitlines())


__all__ = [
    "BodyStructureFaceRow",
    "selected_face_view",
    "format_face_map_lines",
    "default_selected_face_id",
    "build_face_views",
    "BodyStructureFaceView",
    "DEFAULT_SELECTED_FACE_ID",
    "build_body_structure_face_rows",
    "face_role",
    "format_body_structure_face_map",
    "next_face_id",
    "previous_face_id",
    "normalize_selected_face_id",
    "selected_face_row",
]
