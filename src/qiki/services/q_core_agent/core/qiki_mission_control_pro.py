"""Профессиональный CLI-интерфейс Mission Control без внешних библиотек."""

from __future__ import annotations

from qiki.services.q_core_agent.core.mission_control_terminal import MissionControlTerminal


class QIKIMissionControlPro(MissionControlTerminal):
    """Вариант Mission Control Pro на базе текстового терминала."""

    def __init__(self) -> None:
        super().__init__(variant_name="Mission Control Pro")


def main() -> None:
    terminal = QIKIMissionControlPro()
    terminal.run()


if __name__ == "__main__":
    main()
