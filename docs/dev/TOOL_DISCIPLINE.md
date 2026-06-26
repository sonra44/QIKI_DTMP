# TOOL DISCIPLINE — единая методичка агентов (Claude + Codex)

Одна методичка на обоих. `CLAUDE.md` и `AGENTS.md` только указывают сюда + дублируют короткий must-follow блок. Источник истины по дисциплине инструментов — этот файл + sovereign `WORKFLOW_RULES` (recall-proof).

Согласовано Claude + Codex 2026-06-21 после drift-урока: 8 слайсов построены без RAG-grounding, потому что инструменты были доступны, но не использовались по умолчанию (пассивная память не срабатывает в момент действия). Фикс — **форсирующая функция в точке действия (hooks)**, а не «обещать сильнее».

---

## 0. Глобальная задача (не терять)
Строим **QIKI machine-body RUNTIME, доказуемо совпадающий с каноном QIKI Body v0.2.2**. Source-of-truth для канона — repo-docs QIKI Body v0.2.2; **RAGFlow — обязательный retrieval/index слой к этому канону**, а не отдельный источник истины. RAGFlow — НЕ отдельный трек, а канон-фундамент доступа. Evidence-first, «Canon ≠ implemented».

---

## 1. Инвентарь инструментов (что должно работать)
- **CLI:** `herdr`, `qiki-rag` (+`qiki-rag-mcp-smoke`), `docker`, `git`, `python3`, `rg/sed/jq`.
- **MCP (нативные):** `sovereign-memory`, `serena`, `herdr-readonly`, `herdr-cockpit`, `coderabbit`, `ragflow` (stdio-wrapper `qiki_rag_mcp_stdio.py`, ключ из `~/.config/ragflow/qiki-api-key`).
- **Runtime:** Docker `qiki-dev-phase1` (pytest, Docker-first).
- **Native (Claude):** Bash/Read/Edit/Write/Agent/Skill/ToolSearch/AskUserQuestion + deferred (Task/Cron/Monitor/Web/Worktree…).
- **Skills:** срабатывают по `/<имя>` или семантическому совпадению с описанием — ТОЛЬКО из system-reminder available-list, не выдумывать.

`ragflow` через **stdio-wrapper**, НЕ SSE-direct (SSE ловит баг `page_size>100` на tools/list).

---

## 2. Startup-ритуал (ПЕРВОЕ действие любой QIKI-сессии)
0. Стартовая обзорная зона для обоих агентов — `/home/sonra44`, чтобы видеть весь рабочий контур host/projects/tools. Это НЕ значит, что все команды надо выполнять из `/home/sonra44`.
1. **ПЕРВЫЙ ХОД — память, не церемония.** Классифицировать режим задачи (ops / meta-audit / project). Для QIKI project/restore ПЕРВЫМ читать `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md` (LIGHT): classify → `load_context(project="QIKI_DTMP", limit_per_topic=1)` → читать только нужные секции → итог 5-8 строк.
2. `sovereign recall` (load_context / recall) — поднять состояние (часть LIGHT-шага 1).
3. Для QIKI repo-relative команд явно перейти в repo-root: `cd /home/sonra44/QIKI_DTMP && <command>` или выставить `workdir=/home/sonra44/QIKI_DTMP`.
4. **toolcheck/MCP — НЕ ритуал первого хода.** `bash scripts/qiki_toolcheck.sh` + один live-вызов каждого MCP (sovereign · serena · herdr · ragflow) запускать ТОЛЬКО когда задача реально требует проверки инструментария (ops/meta) или инструмент повёл себя странно. Не блокировать ответ на простой вопрос церемонией.
5. **Execution-default:** read-only source-lookup (sovereign / LIGHT / repo / Serena / RAG) делать СРАЗУ, без запроса разрешения у оператора. Разрешение нужно только для мутаций (edit/revert/deploy/деструктив).
6. Прочитать этот файл + must-follow блок в CLAUDE.md/AGENTS.md по мере необходимости.

Рабочее правило cwd:
- `/home/sonra44` — обзор, host/ops/tooling, поиск нужного проекта.
- `/home/sonra44/QIKI_DTMP` — QIKI code/docs/tests/canon/board/runtime.
- другие каталоги (`~/ragflow-work`, `~/.codex`, `~/.claude`, `/tmp` и т.д.) — только когда задача реально относится к ним.

Результат короткий: `SOV=OK SERENA=OK RAG=OK HERDR=OK`.

---

## 3. Доктрина — когда/как
- **sovereign-memory** — состояние/решения/TODO/checkpoints; save + recall-proof. Не канон.
- **serena** — навигация по коду на уровне символов; rg/sed/cat — только вспомогательный быстрый слой (найти файл/конфиг/скрипт), НЕ замена навигации при работе с архитектурным кодом.
- **RAGFlow / qiki-rag** — canon retrieval по QIKI Body v0.2.2.
- **repo-docs** (`docs/design/hardware_and_physics/qiki_body_v0_2_2/*`) — финальная верификация; RAG↔repo расходятся → **repo выигрывает**, RAG-индекс = stale.
- **Docker/tests** — истина реализации (Docker-first).
- **herdr** — **менеджер терминального рабочего пространства / кокпит для AI-агентов (Claude/Codex). Это НЕ tmux.** Управляет workspaces/tabs/панелями и agent-сессиями; координация агентов идёт ЧЕРЕЗ HERDR, а НЕ через tmux (herdr-панели tmux НЕ видит). Назначение: live-наблюдение статуса агентов, отправка им команд/сообщений, чтение вывода, ACK доставки. Отправка агенту: **`herdr pane run <pane> "<text>"`** (текст+Enter); чтение `herdr_read_pane_recent` / `herdr agent read`; статус `herdr agent get`. НЕ `send-text`+`send-keys` (хрупко, не сабмитит).
- **coderabbit / субагенты** — review/поиск дефектов, НЕ источник истины.

### 3.1 HERDR-first coordination

Claude/Codex coordination is HERDR-first, not tmux-first.

- HERDR panes are not necessarily visible through local `tmux`.
- Discover panes with HERDR first: `herdr_list_panes` / `herdr_get_cockpit_digest`.
- Read panes with HERDR: `herdr_read_pane_recent`.
- Send to agents with HERDR: `herdr pane run <pane_id> "<message>"`.
- A sent instruction is not confirmed until HERDR read/status shows an explicit ACK or the agent's new response.
- Use `tmux` only for real tmux sessions/panes, not for HERDR terminal panes unless HERDR explicitly maps them to tmux.

---

## 4. ДВА ОБЯЗАТЕЛЬНЫХ ГЕЙТА (форсятся hooks)
### 4.1 Serena-first (код)
Любой code-claim / review / refactor / архитектурная навигация → СНАЧАЛА serena (find_symbol/get_symbols_overview/find_referencing_symbols). rg/sed допустимы как вспомогательный слой.
**Hard-block:** делать code-claim/review/refactor БЕЗ serena-evidence. Иначе — warn.

### 4.2 RAG-gate (канон)
Любой канон-вывод (IF-ORION / IF-AUDIT / §17 / vocabulary / QIKI Body) → `qiki-rag query → repo-file check → verdict (canon says X; code says Y; fix/no-fix)`.
**Hard-block:** выдавать canon/spec verdict БЕЗ RAG-evidence. Иначе — warn.
Никаких сильных канон-claim из памяти/пересказа.

---

## 5. Hooks (форсинг в точке действия) — block-lite
- **SessionStart** → инжектит этот must-follow + гонит `qiki_toolcheck.sh`.
- **PreToolUse(Bash)** → если команда = broad grep/rg/sed/cat по `src/**.py` → warn «Serena-first».
- **UserPromptSubmit** → если в запросе канон-кейворды (IF-ORION/IF-AUDIT/§17/vocabulary/QIKI Body/canon) → warn «RAG-gate обязателен».

Старт = warning/block-lite, чтобы не ломать ops (где rg нужен до serena). Жёсткий block — только два кейса из §4. Скрипт: `scripts/hooks/tool_discipline_guard.py`.

---

## 6. Checkpoint-дисциплина
sovereign STATUS / DECISIONS / TODO_NEXT + recall-proof (ID). Цикл не закрыт без ID. Docker-first перед заявлением runtime-успеха.

---

## 7. Симметрия
Один контур у обоих: Claude — `.claude/settings.json` hooks + CLAUDE.md указатель; Codex — свои hooks/config + AGENTS.md указатель. Методичка одна (этот файл). Общий smoke: оба доказывают toolcheck ловит live-тулзы + guard срабатывает на fake canon/code path.
