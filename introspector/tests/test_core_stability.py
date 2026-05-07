from __future__ import annotations

from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC, ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from project_introspector import EventEmitter, instrument_function, scan_project
from project_introspector.llm import OpenRouterClient
from project_introspector.models import RuntimeEvent


def test_scan_project_collects_syntax_errors(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")

    snapshot = scan_project(tmp_path, project_name="demo")

    assert [module.module_path for module in snapshot.modules] == ["good"]
    assert len(snapshot.scan_errors) == 1
    assert snapshot.scan_errors[0].module_path == "bad"
    assert snapshot.scan_errors[0].error_type == "SyntaxError"


def test_event_emitter_retains_buffer_when_flush_fails(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.Client, "post", explode)
    emitter = EventEmitter(
        endpoint="http://127.0.0.1:9999/events/runtime",
        project_name="demo",
        batch_size=1,
        fail_open=True,
        register_atexit=False,
    )

    emitter.emit(
        RuntimeEvent(
            event_type="call",
            project_name="demo",
            module_path="demo.module",
            qualified_name="demo.module.fn",
        )
    )

    assert emitter.buffer_size == 1


def test_instrumentation_never_breaks_wrapped_function_when_emitter_fails(monkeypatch) -> None:
    emitter = EventEmitter(endpoint="http://unused", project_name="demo", batch_size=100, register_atexit=False)

    def bad_emit(event):
        raise RuntimeError("emit failed")

    monkeypatch.setattr(emitter, "emit", bad_emit)

    @instrument_function(emitter=emitter, capture_args=True, capture_result=True)
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5


def test_compact_module_fact_exposes_declared_symbols_and_runtime_hotspots() -> None:
    module = scan_project(ROOT / "src", project_name="introspector").modules
    target = next(item for item in module if item.module_path == "project_introspector.runtime")

    payload = OpenRouterClient.compact_module_fact(
        target,
        runtime_symbol_counts={"project_introspector.runtime.instrument_function": 3},
        inbound_dependencies=["project_introspector.__init__"],
    )

    assert payload["runtime_hotspot_candidates"][0]["qualified_name"] == "project_introspector.runtime.instrument_function"
    assert payload["runtime_hotspot_candidates"][0]["runtime_call_count"] == 3
    assert "project_introspector.runtime.instrument_function" in payload["declared_symbols"]["module_functions"]
    assert payload["inbound_dependencies"] == ["project_introspector.__init__"]
