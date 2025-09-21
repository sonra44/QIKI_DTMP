"""Упрощённая версия Mission Control (Fixed) без prompt_toolkit."""

from __future__ import annotations

from qiki.services.q_core_agent.core.mission_control_terminal import MissionControlTerminal


class QIKIMissionControlFixed(MissionControlTerminal):
    """Совместимый с CLI вариант Mission Control Fixed."""

    def __init__(self) -> None:
        super().__init__(variant_name="Mission Control Fixed")


def main() -> None:
    terminal = QIKIMissionControlFixed()
    terminal.run()


if __name__ == "__main__":
    main()
