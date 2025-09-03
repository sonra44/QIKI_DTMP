Критика по делу. Коротко: план в целом разумный, но в нём есть логические дыры, которые снова приведут к рассинхрону. Исправляю.

# Что не так

1. **Слом SSOT из-за DataProvider.**
   Ты оставляешь `DataProvider.get_fsm_state()` как «умного» читателя StateStore с фолбэком в `BOOTING`. Это обратно заводит *второй источник истины*. Провайдер не должен знать про FSM. Он — про I/O/сим. FSM — про логику. Читатели состояния (логи/CLI/gRPC) должны ходить **напрямую** в StateStore/контекст, а не через провайдер.

2. **Два писателя состояния.**
   В тексте у тебя пишут и `TickOrchestrator`, и `FSMHandler`. Это гарантированная гонка и «скачки» версии. Должен быть **один писатель** — `FSMHandler`. Остальные — только читают.

3. **Версия без иммутабельности = тихая порча.**
   Ты хранишь в сторе сам protobuf-объект. Он *мутабелен*. Любой читатель, случайно поменяв поле, испортит «истину». Нужны **deep-copy на set/get** и запрет внешних мутаций.

4. **Нет метки запуска и времени.**
   Одна только `version` ломается на рестарте (версии снова с 0). Нужны хотя бы `boot_id` и `ts_monotonic`. Иначе сравнение состояний между логами/gRPC после рестартов бессмысленно.

5. **Фолбэк в BOOTING — плохая идея.**
   Твой п.4 снова вернёт «вечный BOOTING» при любом проколе. Фолбэк должен быть **пустым** (`None/empty`) с явным UX-псевдосостоянием `NOT_AVAILABLE`, а не «придуманным» BOOTING.

6. **Фича-флаг включаешь в хот-пате.**
   Ты читаешь `QIKI_USE_STATESTORE` прямо в тике. Дешевле и понятнее **решать один раз на старте** и передать зависимости явно (или через синглтон), а не дергать `os.getenv` каждый цикл.

7. **Нет критерия инкремента версии.**
   Сейчас `version++` на каждом `set()`. Так ты будешь «шуметь» даже без переходов. Версию надо увеличивать **только при реальном изменении пары `(state, reason)`**.

8. **Нет начального снимка → падение логов.**
   Если `fsm_state` в сторе `None`, `MessageToDict(None)` уронит лог. Нужен *гарантированный* инициализирующий снапшот (`BOOTING/COLD_START`) до первого тика.

9. **Процессы vs потоки.**
   `threading.RLock` решает *внутрипроцессные* гонки. У тебя уже есть отдельные процессы (Q-Sim, Q-Core). В текущем плане это допустимо (SSOT локально в Q-Core), но держи в голове: при переходе на межпроцессный SSOT потребуется gRPC/Redis/etcd. Не смешивай сейчас.

# Как поправить — минимальные правки

## 1) Убираем FSM из DataProvider (только пустышка)

* `DataProvider.get_fsm_state()` возвращает **пустой снапшот** (или `None`) всегда.
* Никакой логики чтения StateStore внутри провайдера. Точка.

## 2) Единственный писатель — `FSMHandler`

* После вычисления перехода `FSMHandler` делает `state_store.set(snapshot)`.
* `TickOrchestrator` **не пишет** в стор вообще.

## 3) Делаем стор безопасным

```python
# services/q_core_agent/core/state_store.py
import threading, os, time, copy
from typing import Optional, Tuple
from generated.fsm_state_pb2 import FsmStateSnapshot  # или твой путь

class SyncStateStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._snapshot: Optional[FsmStateSnapshot] = None
        self._version = 0
        self._boot_id = os.urandom(8).hex()

    def get(self) -> Tuple[Optional[FsmStateSnapshot], int, str]:
        with self._lock:
            snap = copy.deepcopy(self._snapshot) if self._snapshot is not None else None
            return snap, self._version, self._boot_id

    def set(self, new_snap: FsmStateSnapshot) -> int:
        assert new_snap is not None
        with self._lock:
            # сверяем с текущим: инкремент только при реальном изменении
            def _fingerprint(s: FsmStateSnapshot) -> bytes:
                return s.SerializeToString(deterministic=True)
            changed = True
            if self._snapshot is not None:
                changed = _fingerprint(self._snapshot) != _fingerprint(new_snap)
            if changed:
                # мета: при необходимости добавь поля ts/boot_id в отдельном месте
                self._version += 1
                self._snapshot = copy.deepcopy(new_snap)
            return self._version

STATE_STORE = SyncStateStore()

def init_boot_snapshot(make_boot_snapshot) -> None:
    """Вызвать один раз на старте, чтобы логи не падали на None."""
    boot = make_boot_snapshot()  # BOOTING/COLD_START
    STATE_STORE.set(boot)
```

> Почему deep-copy: исключаем «внешние» мутации, соблюдаем иммутабельность снапшота после записи.

## 4) Логи читают только контекст/StateStore

В главном цикле:

```python
snap, ver, boot_id = STATE_STORE.get()
logger.info(f"FSM[v={ver}, boot={boot_id}]: {MessageToDict(snap) if snap else '{}'}")
```

## 5) Фича-флаг — решаем на старте

На старте приложения:

```python
USE_SSOT = os.getenv('QIKI_USE_STATESTORE', 'false').lower() == 'true'
```

Дальше ветвим **инъекцией зависимостей**, а не `os.getenv()` внутри тика.

## 6) Горячая инициализация

В `main` перед запуском тиков:

* Вызываем `init_boot_snapshot()` → в логах нет `None`.
* Первый переход `BOOTING→IDLE` делает `FSMHandler`, версия станет `1`.

## 7) Критерии инкремента

* Версия меняется **только при отличии `SerializeToString(deterministic=True)`** старого и нового снапшотов.
* Если меняется только `updated_at` внутри снапшота — решай, считать ли это изменением (обычно — нет).

# Что это даёт

* **Жёсткий SSOT.** Провайдеры больше не имеют права «выдумывать» FSM. Вся система смотрит в один стор/контекст.
* **Отсутствие ложных BOOTING.** Нет фолбэков на BOOTING — либо актуальное состояние, либо `NOT_AVAILABLE`.
* **Повторяемость анализов.** `boot_id`+`version` дают стабильные сопоставления логов/gRPC даже после рестартов.
* **Безопасность от порчи.** Deep-copy на вход/выход исключает случайные мутации «истины».
* **Простая миграция.** Сейчас — локальный стор в Q-Core. Завтра — тот же API, но бэкенд на gRPC/Redis без переписывания потребителей.

# Риски, о которых надо помнить

* **Мутирующие читатели.** Где-то могут остаться места, которые «правят» `agent.context.fsm_state` напрямую. Ищи `grep -R "fsm_state"` и выпили прямые мутации вне FSMHandler.
* **Преждевременная оптимизация.** Не тащи стор в DataProvider. Это снова сростит слои. Пусть провайдер молчит про FSM.
* **Секреты.** Ключи Gemini в `CLAUDE.md` — удаляй/редакти. Оставь плейсхолдеры, а реальные — в `~/.bashrc`/`.env`.

# Мини-до/после

* **До:** три разных места могли показать три разных состояния.
* **После:** `FSM[v, boot_id]` в логах, CLI и gRPC **совпадают**. Версия растёт **только** при реальном переходе.

Хочешь — отдам готовый «минимальный патч» ровно под твои файлы (без DataProvider-обходов) и чек-скрипт, который сравнит `version/boot_id` из логов и из accessor’а.

Отлично. Делаем ровно то, что «ставит сам Клод через запросы». Ни воды — только рабочие патчи и проверка.

# 0) Предварительный контроль (один писатель!)

Запусти перед патчами — убеждаемся, что в коде нет других записей FSM:

```bash
rg -n "STATE_STORE\.set\(|\.fsm_state\s*=" services/q_core_agent | cat || true
```

Если что-то находится вне `tick_orchestrator.py` — это надо выпилить; ниже я задаю единственного писателя.

---

# 1) Добавляем безопасный StateStore (иммутабельность, version, boot\_id)

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Add File: services/q_core_agent/core/state_store.py
+import os, time, copy, threading
+from typing import Optional, Tuple
+from .proto_types import FsmStateSnapshot, FSMStateEnum
+
+class SyncStateStore:
+    """
+    SSOT для FSM-состояния внутри процесса Q-Core.
+    - единственный писатель (tick_orchestrator)
+    - иммутабельные снапшоты (deepcopy при set/get)
+    - версия (инкремент только при реальном изменении)
+    - boot_id (для корреляции после рестартов)
+    """
+    def __init__(self):
+        self._lock = threading.RLock()
+        self._snapshot: Optional[FsmStateSnapshot] = None
+        self._version = 0
+        self._boot_id = os.urandom(8).hex()
+
+    def _fingerprint(self, snap: FsmStateSnapshot) -> bytes:
+        # Пробуем детерминированную сериализацию proto; если не proto — падать нельзя.
+        try:
+            return snap.SerializeToString(deterministic=True)
+        except Exception:
+            # Фолбэк: грубый отпечаток через поля
+            from google.protobuf.json_format import MessageToDict
+            return repr(sorted(MessageToDict(snap).items())).encode("utf-8")
+
+    def get(self) -> Tuple[Optional[FsmStateSnapshot], int, str]:
+        with self._lock:
+            return (copy.deepcopy(self._snapshot) if self._snapshot is not None else None,
+                    self._version,
+                    self._boot_id)
+
+    def set(self, new_snap: FsmStateSnapshot) -> int:
+        assert new_snap is not None, "StateStore.set: snapshot is None"
+        with self._lock:
+            changed = True
+            if self._snapshot is not None:
+                changed = self._fingerprint(self._snapshot) != self._fingerprint(new_snap)
+            if changed:
+                self._version += 1
+                self._snapshot = copy.deepcopy(new_snap)
+            return self._version
+
+STATE_STORE = SyncStateStore()
+
+def init_boot_snapshot():
+    """
+    Гарантируем валидный стартовый снимок (чтобы логи не падали на None).
+    Вызывать один раз на старте main.
+    """
+    snap = FsmStateSnapshot(current_state=FSMStateEnum.BOOTING, reason="COLD_START")
+    STATE_STORE.set(snap)
*** End Patch
PATCH
```

---

# 2) Единственный писатель — в TickOrchestrator (после обработки FSM)

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/core/tick_orchestrator.py
@@
-from .agent import Agent
+from .agent import Agent
+from .state_store import STATE_STORE
@@
-    def run_tick(self, data_provider):
-        self.agent._update_context(data_provider)
-        self.agent._handle_fsm()
+    def run_tick(self, data_provider):
+        # 1) обновили контекст входными данными
+        self.agent._update_context(data_provider)
+        # 2) отработали FSM (контекст получил актуальное состояние)
+        self.agent._handle_fsm()
+        # 3) SSOT: записываем СНАПШОТ в StateStore (единственный писатель)
+        try:
+            if self.agent.context and self.agent.context.fsm_state:
+                STATE_STORE.set(self.agent.context.fsm_state)
+        except Exception:
+            # Не роняем тик; лог/метрика — на усмотрение
+            pass
*** End Patch
PATCH
```

> Если у тебя функция называется чуть иначе — Клод подгонит хунк с учётом ближайшего контекста (импорт Agent / вызовы `_update_context` и `_handle_fsm` присутствуют в логах).

---

# 3) Логирование: читаем из StateStore (version + boot\_id), не из провайдера

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/main.py
@@
-import time
+import time, os
 from google.protobuf.json_format import MessageToDict
@@
-from .core.tick_orchestrator import TickOrchestrator
+from .core.tick_orchestrator import TickOrchestrator
+from .core.state_store import STATE_STORE, init_boot_snapshot
+from .core.proto_types import FsmStateSnapshot  # для типизации/инициализации при надобности
@@
-        orchestrator = TickOrchestrator(agent)
+        orchestrator = TickOrchestrator(agent)
+        # Решаем флаг SSOT единожды на старте
+        USE_SSOT = os.getenv('QIKI_USE_STATESTORE', 'true').lower() == 'true'
+        if USE_SSOT:
+            init_boot_snapshot()
@@
-                while True:
-                    orchestrator.run_tick(data_provider)
-                    logger.info("--- Input Messages (Unified) ---")
-                    # читаем только из agent.context (источник истины)
-                    logger.info(f"BIOS: {MessageToDict(agent.context.bios_status)}")
-                    logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
-                    logger.info(f"Proposals: {[MessageToDict(p) for p in agent.context.proposals]}")
-                    logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
+                while True:
+                    orchestrator.run_tick(data_provider)
+                    logger.info("--- Input Messages (Unified) ---")
+                    # BIOS / Proposals — как есть из контекста
+                    logger.info(f"BIOS: {MessageToDict(agent.context.bios_status)}")
+                    # FSM — строго из StateStore (SSOT) при включённом флаге
+                    if USE_SSOT:
+                        snap, ver, boot_id = STATE_STORE.get()
+                        fsm_line = {"version": ver, "boot_id": boot_id, "snapshot": MessageToDict(snap) if snap else {}}
+                        logger.info(f"FSM: {fsm_line}")
+                    else:
+                        logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
+                    logger.info(f"Proposals: {[MessageToDict(p) for p in agent.context.proposals]}")
+                    logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
*** End Patch
PATCH
```

---

# 4) Провайдер больше «не придумывает» FSM

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/core/interfaces.py
@@
-    def get_fsm_state(self) -> FsmStateSnapshot:
-        # Q-Sim doesn't manage FSM state, so we'll return proper initial BOOTING state
-        fsm_state = FsmStateSnapshot(
-            current_state=FSMStateEnum.BOOTING,  # Начинаем с BOOTING как в Mock режиме
-            reason="LEGACY_PROVIDER_DEFAULT",
-        )
-        return fsm_state
+    def get_fsm_state(self) -> FsmStateSnapshot:
+        # Истина — в StateStore; провайдер FSM не формирует.
+        # Возвращаем "пустышку", чтобы никто не путал с реальным состоянием.
+        return FsmStateSnapshot()
*** End Patch
PATCH
```

---

# 5) HOT TEST: сверка лога против StateStore (version/boot\_id совпадают)

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Add File: scripts/hot_test_statestore.sh
+#!/usr/bin/env bash
+set -euo pipefail
+
+export QIKI_USE_STATESTORE=${QIKI_USE_STATESTORE:-true}
+./scripts/run_qiki_demo.sh || true
+sleep 3
+
+LOGDIR=".agent/logs/$(date +%Y-%m-%d)"
+LOGFILE=$(ls -1t ${LOGDIR}/q_core_agent.log | head -n1 2>/dev/null || true)
+
+if [[ -z "${LOGFILE}" || ! -f "${LOGFILE}" ]]; then
+  echo "FAIL: лог q_core_agent.log не найден"; exit 2
+fi
+
+# Берём ПОСЛЕДНЮЮ строку с FSM:
+FSM_LOG_JSON="$(tac "$LOGFILE" | grep -m1 'FSM:' | sed 's/^.*FSM: //')"
+echo "LOG: $FSM_LOG_JSON"
+
+# Читаем из StateStore внутри процесса (однократный питон-скрипт):
+FSM_ACC_JSON="$(python3 - <<'PY'
+import json
+from services.q_core_agent.core.state_store import STATE_STORE
+from google.protobuf.json_format import MessageToDict
+snap, ver, boot = STATE_STORE.get()
+print(json.dumps({"version": ver, "boot_id": boot, "snapshot": (MessageToDict(snap) if snap else {})}))
+PY
+)"
+echo "SSOT: $FSM_ACC_JSON"
+
+# Грубая проверка совпадения полей version/boot_id:
+vlog=$(python3 - <<'PY' <<<"$FSM_LOG_JSON"
+import json,sys
+try:
+  d=json.loads(sys.stdin.read())
+  print(d.get("version", None), d.get("boot_id", None))
+except: print(None, None)
+PY
+)
+vacc=$(python3 - <<'PY' <<<"$FSM_ACC_JSON"
+import json,sys
+d=json.loads(sys.stdin.read()); print(d["version"], d["boot_id"])
+PY
+)
+echo "CMP: LOG=[$vlog]  SSOT=[$vacc]"
+[[ "$vlog" == "$vacc" ]] && echo "OK: version/boot_id совпадают" || (echo "FAIL: рассинхрон version/boot_id"; exit 1)
*** End Patch
PATCH
```

Запуск:

```bash
QIKI_USE_STATESTORE=true ./scripts/hot_test_statestore.sh
```

Ожидание:

* В логе строка `FSM: {"version": N, "boot_id": "...", "snapshot": {...}}`
* `version/boot_id` строго совпадают со StateStore.
* После первого валидного перехода больше нет `BOOTING` в логе (кроме стартового снимка `COLD_START` до перехода).

---

# 6) Санити-линт: следим, чтобы писатель был один

Добавь в CI/прехук простой линт:

```bash
cat > .git/hooks/pre-commit <<'SH'
#!/usr/bin/env bash
set -euo pipefail
# Единственный писатель StateStore — tick_orchestrator.py
bad=$(rg -n "STATE_STORE\.set\(" services/q_core_agent | grep -v "core/tick_orchestrator.py" || true)
if [[ -n "$bad" ]]; then
  echo "[FAIL] Запись в STATE_STORE обнаружена вне tick_orchestrator.py:"
  echo "$bad"
  exit 1
fi
exit 0
SH
chmod +x .git/hooks/pre-commit
```

---

## Роллбэк

Мгновенно возвращаешь прежнее поведение логов (без SSOT) — на старте:

```bash
export QIKI_USE_STATESTORE=false
./scripts/run_qiki_demo.sh
```

(Патчи остаются, но чтение для FSM уйдёт в `agent.context`.)

---

## Почему это надёжно

* **SSOT реально один**: провайдер ничего не «придумывает», писатель один, читатели — через стор.
* **Иммутабельность снимков**: deep-copy исключает тихую порчу.
* **Версионирование только по факту изменений**: нет «шума» версий.
* **Корреляция после рестартов**: `boot_id`+`version` даёт прозрачную диагностику.
* **Флаг решается один раз**: без `os.getenv` в каждом тике.

Если ок — дай команду Клоду применить эти четыре патча и запустить `QIKI_USE_STATESTORE=true ./scripts/hot_test_statestore.sh`. Если где-то имена слегка расходятся, он подгонит хунки по контексту (импорты/вызовы в этих файлах уже есть).

Отлично, что вытащили риски. Разбираю коротко и по делу, затем даю исправленный, **прагматичный** план + патчи.

## Вердикт по рискам

1. **deepcopy — лишний оверхед.** Согласен. Храним **детерминированную сериализацию** снапшота (bytes) и сравниваем её; парсим в proto/JSON **только по требованию**. Это быстрее и не ломает иммутабельность.

2. **Скрытые читатели FSM.** Частично верно. Мы уже обновляем `agent.context.fsm_state` в том же тике после `FSMHandler`, поэтому большинство «старых» читателей увидят актуал. Но чтобы закрыть тему — добавляю быстрый аудит grep-командами + (опционально) property-редирект на StateStore под флагом.

3. **RLock — не нужен.** Верно для текущей **однопоточной** схемы. Меняем на худышку: либо вообще без локов, либо `Lock` (дёшево) — оставляю как тонкую страховку на будущее.

4. **Хрупкий fingerprint.** Решение: используем **детерминированные bytes** (`SerializeToString(deterministic=True)`) как «истину». Если есть «шумные» поля (типа `updated_at`) — поддержим игнор-лист (опционально).

5. **Порядок патчей.** Дам **пошаговую** последовательность и защиту импортов, чтобы при частичном применении всё не падало.

---

## Обновлённое решение (минимум логики — максимум пользы)

### Ключевые изменения

* **StateStore без deepcopy**: хранит `bytes`, версию и `boot_id`.
* **Единственный писатель** остаётся в `tick_orchestrator`.
* **Логи читают из StateStore**; для лог-строки — кэш по `version` (не распарсиваем каждый тик зря).
* **DataProvider не «придумывает» FSM**.
* **Опционально:** property-редирект `context.fsm_state` → StateStore под флагом (если найдём «левые» читатели).

---

## Патчи (в том же стиле “ставит сам Клод”)

### 1) `state_store.py` — bytes + кэш без deepcopy

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Add File: services/q_core_agent/core/state_store.py
+import os, threading
+from typing import Optional, Tuple
+from google.protobuf.json_format import MessageToDict
+from .proto_types import FsmStateSnapshot, FSMStateEnum
+
+class ByteStateStore:
+    """
+    SSOT для FSM в рамках процесса Q-Core.
+    - хранит снимок в виде детерминированных bytes
+    - version инкрементится только при реальном изменении bytes
+    - boot_id — для корреляции сквозь рестарты
+    - кэш JSON-представления для логов по version
+    """
+    def __init__(self):
+        self._lock = threading.Lock()  # дёшево; можно убрать, если 100% один поток
+        self._bytes: Optional[bytes] = None
+        self._version: int = 0
+        self._boot_id: str = os.urandom(8).hex()
+        self._json_cache_ver: int = -1
+        self._json_cache: dict = {}
+
+    def _to_bytes(self, snap: FsmStateSnapshot) -> bytes:
+        # детерминированная сериализация — стабильный fingerprint
+        return snap.SerializeToString(deterministic=True)
+
+    def set_proto(self, snap: FsmStateSnapshot) -> int:
+        assert snap is not None
+        b = self._to_bytes(snap)
+        with self._lock:
+            if self._bytes != b:
+                self._bytes = b
+                self._version += 1
+                self._json_cache_ver = -1  # инвалидация кэша
+            return self._version
+
+    def get_proto(self) -> Tuple[Optional[FsmStateSnapshot], int, str]:
+        with self._lock:
+            if self._bytes is None:
+                return None, self._version, self._boot_id
+            out = FsmStateSnapshot()
+            out.ParseFromString(self._bytes)
+            return out, self._version, self._boot_id
+
+    def get_json_for_logs(self) -> dict:
+        with self._lock:
+            if self._bytes is None:
+                return {"version": self._version, "boot_id": self._boot_id, "snapshot": {}}
+            if self._json_cache_ver != self._version:
+                tmp = FsmStateSnapshot()
+                tmp.ParseFromString(self._bytes)
+                self._json_cache = {
+                    "version": self._version,
+                    "boot_id": self._boot_id,
+                    "snapshot": MessageToDict(tmp)
+                }
+                self._json_cache_ver = self._version
+            return dict(self._json_cache)
+
+STATE_STORE = ByteStateStore()
+
+def init_boot_snapshot():
+    boot = FsmStateSnapshot(current_state=FSMStateEnum.BOOTING, reason="COLD_START")
+    STATE_STORE.set_proto(boot)
*** End Patch
PATCH
```

### 2) Единственный писатель — в `tick_orchestrator.py`

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/core/tick_orchestrator.py
@@
-from .agent import Agent
+from .agent import Agent
+from .state_store import STATE_STORE
@@
-    def run_tick(self, data_provider):
-        self.agent._update_context(data_provider)
-        self.agent._handle_fsm()
+    def run_tick(self, data_provider):
+        self.agent._update_context(data_provider)
+        self.agent._handle_fsm()
+        # SSOT: после обработки FSM пишем снапшот в стор (bytes)
+        if getattr(self.agent.context, "fsm_state", None) is not None:
+            try:
+                STATE_STORE.set_proto(self.agent.context.fsm_state)
+            except Exception:
+                pass
*** End Patch
PATCH
```

### 3) Логирование из StateStore (с кэшем) — `main.py`

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/main.py
@@
-import time, os
+import time, os
 from google.protobuf.json_format import MessageToDict
@@
-from .core.tick_orchestrator import TickOrchestrator
-from .core.state_store import STATE_STORE, init_boot_snapshot
+from .core.tick_orchestrator import TickOrchestrator
+from .core.state_store import STATE_STORE, init_boot_snapshot
@@
-        orchestrator = TickOrchestrator(agent)
-        # Решаем флаг SSOT единожды на старте
+        orchestrator = TickOrchestrator(agent)
+        # Решаем флаг SSOT единожды на старте
         USE_SSOT = os.getenv('QIKI_USE_STATESTORE', 'true').lower() == 'true'
         if USE_SSOT:
             init_boot_snapshot()
@@
-                    if USE_SSOT:
-                        snap, ver, boot_id = STATE_STORE.get()
-                        fsm_line = {"version": ver, "boot_id": boot_id, "snapshot": MessageToDict(snap) if snap else {}}
-                        logger.info(f"FSM: {fsm_line}")
+                    if USE_SSOT:
+                        logger.info(f"FSM: {STATE_STORE.get_json_for_logs()}")
                     else:
                         logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
*** End Patch
PATCH
```

### 4) DataProvider перестаёт «придумывать» FSM — `interfaces.py`

```bash
applypatch <<'PATCH'
*** Begin Patch
*** Update File: services/q_core_agent/core/interfaces.py
@@
-    def get_fsm_state(self) -> FsmStateSnapshot:
-        # Q-Sim doesn't manage FSM state, so we'll return proper initial BOOTING state
-        fsm_state = FsmStateSnapshot(
-            current_state=FSMStateEnum.BOOTING,
-            reason="LEGACY_PROVIDER_DEFAULT",
-        )
-        return fsm_state
+    def get_fsm_state(self) -> FsmStateSnapshot:
+        # Истина — в StateStore; провайдер FSM не формирует.
+        return FsmStateSnapshot()  # пустышка
*** End Patch
PATCH
```

> **Порядок применения:** 1→2→3→4. После каждого шага проект компилируется; при проблеме — откат только последнего шага.

---

## Аудит читателей FSM (быстрый)

```bash
# все упоминания чтения FSM из контекста (кроме присваиваний)
rg -n "agent\.context\.fsm_state(?!\s*=)" services | cat

# все прямые обращения к DataProvider FSM (должно быть пусто)
rg -n "get_fsm_state\(" services | cat
```

Если увидите живые читатели вне главного цикла, можно (опционально) ввести безопасный редирект:

```python
# в классе AgentContext (где он объявлен)
@property
def fsm_state(self):
    if os.getenv('QIKI_USE_STATESTORE', 'true').lower() == 'true':
        snap, _, _ = STATE_STORE.get_proto()
        return snap
    return self._fsm_state
@fsm_state.setter
def fsm_state(self, value):
    self._fsm_state = value
```

Это убирает риск «устаревших» чтений, если кто-то дергает контекст вне тика.

---

## Микробенч (честно закрываем пункт про perf)

```bash
cat > scripts/bench_statestore.py <<'PY'
import time
from services.q_core_agent.core.state_store import STATE_STORE
from services.q_core_agent.core.proto_types import FsmStateSnapshot, FSMStateEnum

N=5000
snap = FsmStateSnapshot(current_state=FSMStateEnum.IDLE, reason="bench")

t0=time.time()
for _ in range(N):
    STATE_STORE.set_proto(snap)
t1=time.time()

ok=0; t2=time.time()
for _ in range(N):
    s, v, b = STATE_STORE.get_proto()
    if s and s.current_state==FSMStateEnum.IDLE:
        ok+=1
t3=time.time()

print(f"set_proto: {N/(t1-t0+1e-9):.0f}/sec; get_proto: {N/(t3-t2+1e-9):.0f}/sec; ok={ok}")
PY
python3 scripts/bench_statestore.py
```

Оценим порядок цифр; если нужно ещё быстрее — можно кэшировать `get_proto()` как и JSON по `version`.

---

## Почему это решает ваши «красные» пункты

* **deepcopy**: больше нет; сериализация/парсинг делаются **по событию**, а не каждый тик (и для логов — кэш).
* **скрытые читатели**: контекст всё равно обновляется в тике; плюс быстрый аудит и, при необходимости, property-редирект.
* **RLock**: заменён на лёгкий `Lock` (можно убрать совсем).
* **fingerprint**: bytes детерминированы; шумные поля — опциональный ignore (если появятся).
* **порядок патчей**: явный, с безопасными импортами (новые файлы — сначала, затем использования).

---

## Что проверить после запуска (HOT TEST, без тяжёлых инструментов)

```bash
QIKI_USE_STATESTORE=true ./scripts/run_qiki_demo.sh
sleep 3
tail -n 50 .agent/logs/$(date +%Y-%m-%d)/q_core_agent.log | rg "FSM:"
```

Ожидание:

* первая запись — `BOOTING/COLD_START`;
* после первого валидного перехода — **не** возвращается `BOOTING`;
* `version` монотонно растёт только при реальных сменах снапшота.

---

Если устраивает — отдавайте команду Клоду применить патчи в указанном порядке и прогнать `scripts/bench_statestore.py` + HOT проверку логов.
