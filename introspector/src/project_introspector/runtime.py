from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any, Callable, ParamSpec, TypeVar

from .emitter import EventEmitter
from .models import RuntimeEvent

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def configure_otel(service_name: str, endpoint: str | None = None) -> bool:
    """Best-effort OpenTelemetry setup.

    Returns True when OpenTelemetry packages are available and configuration was applied.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return False

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return True


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _shape(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, (list, tuple, set)):
        return type(value).__name__
    return type(value).__name__


def _capture_arg_shapes(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, str]:
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs)
    except Exception:
        return {f"arg{index}": _shape(value) for index, value in enumerate(args)} | {
            key: _shape(value) for key, value in kwargs.items()
        }
    return {name: _shape(value) for name, value in bound.arguments.items()}


def _emit_safely(emitter: EventEmitter, event: RuntimeEvent) -> None:
    try:
        emitter.emit(event)
    except Exception:
        logger.warning("project-introspector runtime emit failed", exc_info=True)


def instrument_function(
    emitter: EventEmitter,
    capture_args: bool = False,
    capture_result: bool = False,
    extra_tags: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    extra_tags = extra_tags or {}

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        module_path = func.__module__
        qualified_name = f"{module_path}.{func.__qualname__}"

        try:
            from opentelemetry import trace

            tracer = trace.get_tracer(__name__)

            def span_factory():
                return tracer.start_as_current_span(qualified_name)
        except Exception:
            span_factory = _NullContext

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                started = time.perf_counter()
                args_shape = _capture_arg_shapes(func, args, kwargs) if capture_args else {}
                try:
                    with span_factory():
                        result = await func(*args, **kwargs)
                except Exception as exc:
                    _emit_safely(
                        emitter,
                        RuntimeEvent(
                            event_type="error",
                            project_name=emitter.project_name,
                            module_path=module_path,
                            qualified_name=qualified_name,
                            duration_ms=(time.perf_counter() - started) * 1000,
                            args_shape=args_shape,
                            exception_type=type(exc).__name__,
                            tags=extra_tags,
                        ),
                    )
                    raise

                _emit_safely(
                    emitter,
                    RuntimeEvent(
                        event_type="call",
                        project_name=emitter.project_name,
                        module_path=module_path,
                        qualified_name=qualified_name,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        args_shape=args_shape,
                        result_shape=_shape(result) if capture_result else None,
                        tags=extra_tags,
                    ),
                )
                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = time.perf_counter()
            args_shape = _capture_arg_shapes(func, args, kwargs) if capture_args else {}
            try:
                with span_factory():
                    result = func(*args, **kwargs)
            except Exception as exc:
                _emit_safely(
                    emitter,
                    RuntimeEvent(
                        event_type="error",
                        project_name=emitter.project_name,
                        module_path=module_path,
                        qualified_name=qualified_name,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        args_shape=args_shape,
                        exception_type=type(exc).__name__,
                        tags=extra_tags,
                    ),
                )
                raise

            _emit_safely(
                emitter,
                RuntimeEvent(
                    event_type="call",
                    project_name=emitter.project_name,
                    module_path=module_path,
                    qualified_name=qualified_name,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    args_shape=args_shape,
                    result_shape=_shape(result) if capture_result else None,
                    tags=extra_tags,
                ),
            )
            return result

        return sync_wrapper

    return decorator
