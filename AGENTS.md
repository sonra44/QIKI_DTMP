# QIKI_DTMP — инструкции для Codex (память / старт)

Основные “глобальные” триггеры лежат в `~/.codex/AGENTS.md`.

## MCP память (QIKI_DTMP)

- MCP сервер: `sovereign-memory` (Codex подключается по streamable HTTP `/mcp`).
- Триггерная цепочка “ПРОЧТИ ЭТО”: `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md`.
- Перед выполнением любой большой задачи сначала подними контекст через `recall_memory`.
- В конце сессии сохрани `STATUS` и `TODO NEXT` как `episodic`, решения — как `core`.
