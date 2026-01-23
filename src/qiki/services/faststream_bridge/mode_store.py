from __future__ import annotations

import os
import threading

from qiki.shared.models.qiki_chat import QikiMode


_lock = threading.Lock()
_mode: QikiMode = QikiMode(os.getenv("QIKI_MODE", QikiMode.FACTORY.value))


def get_mode() -> QikiMode:
    with _lock:
        return _mode


def set_mode(mode: QikiMode) -> None:
    global _mode
    with _lock:
        _mode = mode


def reset_for_tests() -> None:
    set_mode(QikiMode.FACTORY)

