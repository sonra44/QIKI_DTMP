"""Ultimate-версия Mission Control в чистом CLI-варианте."""

from __future__ import annotations

from qiki.services.q_core_agent.core.mission_control_terminal import MissionControlTerminal


class QIKIMissionControlUltimate(MissionControlTerminal):
    """Расширенная CLI-версия Mission Control Ultimate."""

    def __init__(self) -> None:
        super().__init__(variant_name="Mission Control Ultimate")


def main() -> None:
    terminal = QIKIMissionControlUltimate()
    terminal.run()


if __name__ == "__main__":
    main()
