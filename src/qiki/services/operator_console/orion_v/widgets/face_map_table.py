"""Textual DataTable renderer for the QIKI Body Face Map F00-F11."""

from __future__ import annotations

from textual.widgets import DataTable

from qiki.services.operator_console.orion_v.body_structure_face_map import (
    BodyStructureFaceRow,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
)


class FaceMapTable(DataTable):
    """Face Map table widget.

    Uses Textual DataTable so F2 is an actual terminal UI table rather than a
    hand-formatted string block. The data remains the existing local
    body-structure view model.
    """

    DEFAULT_CSS = """
    FaceMapTable {
        height: 16;
        min-width: 38;
        border: round $surface-lighten-1 30%;
    }
    """

    def __init__(self, vm: BodyStructureConsoleViewModel, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._columns_added = False
        self._vm = vm

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.update_view_model(self._vm)

    def update_view_model(self, vm: BodyStructureConsoleViewModel) -> None:
        self._vm = vm
        if not self._columns_added:
            self.add_columns("face_id", "role", "occupancy", "module")
            self._columns_added = True
        self.clear()
        for row in vm.faces:
            self.add_row(*_row_values(row), key=row.face_id)
        try:
            selected_index = next(
                index for index, row in enumerate(vm.faces) if row.face_id == vm.selected_face_id
            )
            self.cursor_coordinate = (selected_index, 0)
        except StopIteration:
            return


def _row_values(row: BodyStructureFaceRow) -> tuple[str, str, str, str]:
    marker = ">" if row.selected else " "
    occupancy = "OCCUPIED" if row.occupancy == "occupied" else row.occupancy
    module = row.module_id or "-"
    return (f"{marker} {row.face_id}", row.role, occupancy, module)
