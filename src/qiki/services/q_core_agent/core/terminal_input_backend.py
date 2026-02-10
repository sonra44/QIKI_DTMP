"""Terminal input backends for replay/live radar controls."""

from __future__ import annotations

import os
import select
import shutil
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InputEvent:
    kind: str
    key: str = ""
    raw: str = ""
    x: float = 0.0
    y: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    delta: float = 0.0


class TerminalInputBackend(Protocol):
    @property
    def name(self) -> str:
        ...

    def poll_events(self, timeout_ms: int) -> list[InputEvent]:
        ...

    def close(self) -> None:
        ...


class LineInputBackend:
    """Portable command-line backend (always works over SSH/tmux)."""

    @property
    def name(self) -> str:
        return "line"

    def poll_events(self, timeout_ms: int) -> list[InputEvent]:
        _ = timeout_ms
        try:
            raw = input("replay> ").strip().lower()
        except EOFError:
            return [InputEvent(kind="key", key="q")]
        if not raw:
            return []
        return [InputEvent(kind="line", raw=raw)]

    def close(self) -> None:
        return


class RealTerminalInputBackend:
    """Raw terminal backend with key/mouse events (capability upgrade)."""

    _ENABLE_MOUSE = "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
    _DISABLE_MOUSE = "\x1b[?1006l\x1b[?1002l\x1b[?1000l"

    def __init__(self) -> None:
        self._fd = sys.stdin.fileno()
        self._old_attrs = termios.tcgetattr(self._fd)
        self._buffer = ""
        self._closed = False
        self._last_mouse: tuple[float, float] | None = None
        tty.setcbreak(self._fd)
        sys.stdout.write(self._ENABLE_MOUSE)
        sys.stdout.flush()

    @property
    def name(self) -> str:
        return "real-terminal"

    @classmethod
    def is_supported(cls) -> tuple[bool, str]:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False, "stdin/stdout is not TTY"
        if os.getenv("TERM", "").lower() == "dumb":
            return False, "TERM=dumb"
        return True, ""

    @classmethod
    def create_or_none(cls) -> tuple[RealTerminalInputBackend | None, str]:
        ok, reason = cls.is_supported()
        if not ok:
            return None, reason
        try:
            return cls(), ""
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def poll_events(self, timeout_ms: int) -> list[InputEvent]:
        if self._closed:
            return []
        timeout_s = max(0.0, timeout_ms / 1000.0)
        ready, _, _ = select.select([self._fd], [], [], timeout_s)
        if not ready:
            return []
        try:
            chunk = os.read(self._fd, 4096).decode("utf-8", errors="ignore")
        except OSError:
            return []
        if not chunk:
            return []
        self._buffer += chunk
        return self._drain_events()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_attrs)
        except Exception:  # noqa: BLE001
            pass
        try:
            sys.stdout.write(self._DISABLE_MOUSE)
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass

    def _drain_events(self) -> list[InputEvent]:
        events: list[InputEvent] = []
        while self._buffer:
            if self._buffer.startswith("\x1b[<"):
                parsed = self._parse_sgr_mouse()
                if parsed is None:
                    break
                if parsed:
                    events.append(parsed)
                continue
            if self._buffer.startswith("\x1b["):
                parsed_key = self._parse_special_key()
                if parsed_key is None:
                    break
                if parsed_key:
                    events.append(parsed_key)
                continue
            char = self._buffer[0]
            self._buffer = self._buffer[1:]
            if char in {"\r", "\n"}:
                continue
            if char == "\x03":
                events.append(InputEvent(kind="key", key="q"))
                continue
            events.append(InputEvent(kind="key", key=char.lower()))
        return events

    def _parse_special_key(self) -> InputEvent | None:
        mapping = {
            "\x1b[A": "up",
            "\x1b[B": "down",
            "\x1b[C": "right",
            "\x1b[D": "left",
        }
        for token, key in mapping.items():
            if self._buffer.startswith(token):
                self._buffer = self._buffer[len(token) :]
                return InputEvent(kind="key", key=key)
        if len(self._buffer) < 2:
            return None
        # Drop unknown escape sequence prefix.
        self._buffer = self._buffer[1:]
        return None

    def _parse_sgr_mouse(self) -> InputEvent | None:
        terminator_index = max(self._buffer.find("M"), self._buffer.find("m"))
        if terminator_index == -1:
            return None
        token = self._buffer[: terminator_index + 1]
        self._buffer = self._buffer[terminator_index + 1 :]
        # Expected: ESC [ < Cb ; Cx ; Cy M/m
        try:
            payload = token[3:-1]
            code_s, x_s, y_s = payload.split(";")
            code = int(code_s)
            col = int(x_s)
            row = int(y_s)
        except Exception:  # noqa: BLE001
            return InputEvent(kind="noop")
        x, y = self._normalize_xy(col, row)
        is_release = token.endswith("m")
        is_wheel = bool(code & 64)
        is_motion = bool(code & 32)
        button = code & 3
        if is_wheel:
            if button == 0:
                return InputEvent(kind="wheel", delta=1.0)
            if button == 1:
                return InputEvent(kind="wheel", delta=-1.0)
            return InputEvent(kind="noop")
        if is_motion:
            last = self._last_mouse
            self._last_mouse = (x, y)
            if last is None:
                return InputEvent(kind="noop")
            dx = x - last[0]
            dy = y - last[1]
            return InputEvent(kind="drag", dx=dx, dy=dy)
        self._last_mouse = (x, y)
        if not is_release and button == 0:
            return InputEvent(kind="click", x=x, y=y)
        return InputEvent(kind="noop")

    @staticmethod
    def _normalize_xy(col: int, row: int) -> tuple[float, float]:
        size = shutil.get_terminal_size(fallback=(120, 40))
        max_cols = max(1, size.columns)
        max_rows = max(1, size.lines)
        x = ((float(col) / float(max_cols)) * 2.0) - 1.0
        y = 1.0 - ((float(row) / float(max_rows)) * 2.0)
        return x, y


def select_input_backend(*, prefer_real: bool) -> tuple[TerminalInputBackend, str]:
    """Select input backend with graceful fallback to line mode."""

    if not prefer_real:
        return LineInputBackend(), ""
    backend, reason = RealTerminalInputBackend.create_or_none()
    if backend is not None:
        return backend, ""
    warning = f"Real input backend unavailable ({reason}); fallback to line mode."
    if os.getenv("TMUX"):
        warning += " In tmux enable mouse passthrough for wheel/click/drag."
    return LineInputBackend(), warning

