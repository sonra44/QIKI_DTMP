from __future__ import annotations

from typing import Awaitable, Callable, Dict, Generic, TypeVar

StateT = TypeVar("StateT")
PayloadT = TypeVar("PayloadT")


class FSMEngine(Generic[StateT, PayloadT]):
    """Базовый движок FSM с реестром ``state -> handler``."""

    def __init__(self) -> None:
        self._registry: Dict[StateT, Callable[[PayloadT], Awaitable[PayloadT]]] = {}

    def register(
        self, state: StateT, handler: Callable[[PayloadT], Awaitable[PayloadT]]
    ) -> None:
        """Регистрация обработчика для состояния."""
        self._registry[state] = handler

    async def process_transition(self, state: StateT, payload: PayloadT) -> PayloadT:
        """Выполнить переход для указанного состояния."""
        handler = self._registry.get(state)
        if handler is None:
            raise ValueError(f"No handler registered for state {state!r}")
        return await handler(payload)
