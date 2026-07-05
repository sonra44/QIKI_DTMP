# F5 «QIKI / ДИАЛОГ» — системный дизайн от логики до интерфейса

Статус: **УТВЕРЖДЁН ОПЕРАТОРОМ 2026-07-04** (внедрение milestone за milestone; H0 выполнен 2026-07-04, live-proof: ss → 127.0.0.1).
Дата: 2026-07-04. База: `ПАЧИ/030726/F5_REBASED_20260703.md` + верификация кодом (этот документ).
Верификация: каждое утверждение о текущем состоянии проверено по живому коду/рантайму 2026-07-04.

---

## 1. Законы (неизменные, из канона)

1. **Текст провайдера ≠ правда runtime. Кандидат ≠ pending action ≠ effect confirmation** (ADR-0015).
2. Вывод чата всегда распадается на 4 сущности: **диалог / кандидат / предпросмотр решения / улика**.
3. Правда распределена: мир — q-sim; решения — QIKI policy (детерминированная); оператор — гость;
   ORION показывает (`bot_source_of_truth.md §1`).
4. **CaMeL-граница**: недоверенный вывод модели никогда не владеет control flow. Провайдер —
   «карантин», производит только данные с capability-метками (source/trust/freshness/claim).
5. Словарь доверия — канон `06_INTERFACE_CONTROL.md §15.5`:
   `trusted / degraded / conflicting / blind / stale / missing / local_reconstruction / hypothesis`
   (+ принятый в консоли `fixture_only`). Новые значения — только ADR + RAG-gate.
   *Поправка к ребейзу: ссылки «§17» в прежних доках нормализовать на §15.5.*
6. ORION evidence-контракт — `06_INTERFACE_CONTROL.md §19 IF-ORION-EVIDENCE-001`.
7. F5 — игровое поле по-русски; коды остаются кодами (DISPLAY_CANON, языковая рамка).

## 2. Верифицированное текущее состояние (код, 2026-07-04)

### 2.1 Уже построено (мост к телу готов, строить заново НЕ надо)
| Контур | Файл-свидетель |
|---|---|
| Face Map / занятость граней | `orion_v/body_structure_view_model.py` (`body_structure_face_map`) |
| Attach lifecycle + паспорта | там же (`run_attach_pipeline`, слайсы 0001-0008) |
| Evidence Card (audit-backed) | там же + `evidence_card*` |
| Mass/CoM/Inertia честный pending | `cockpit_playable_view_model.py` (`body_physics_view_model`) |
| PDU/thermal gating | `pdu_evidence.py`, `power_thermal_view_model.py` |
| v1-шина intent→response | `qiki.intents` → `qiki.responses.qiki`, корреляция request_id (живая) |
| Голос QIKI в кокпите (№8в) | `qiki_voice.py`: лента ACK/REJECT/INFO, коды в tooltip (60adeee) |
| LLM-провайдер | `neural_engine.py` (OpenAI-клиент реальный, mock off), LLM-actions вырезаются `_strip_actions_for_proposals_only` (стр. 43, 190) |

### 2.2 Дыры безопасности (BLOCKER'ы — подтверждены)
| # | Дыра | Свидетель | Статус проверки |
|---|---|---|---|
| Д1 | Ключ OpenAI по неаутентифицированной шине: `set_key` → `os.environ` | `nats_subjects.py:37`; `qiki_orion_intents_service.py:3940-3944` | подтверждено кодом |
| Д2 | NATS без auth; любой клиент публикует в `qiki.responses.qiki` и драйвит `_qiki_pending_action` | compose-файлы; **живое доказательство 2026-07-04**: publish из qiki-dev дошёл до консоли (smoke №8в) | подтверждено живьём |
| Д2+ | **ХУЖЕ ребейза**: дефолтный `docker-compose.yml` публикует `4222:4222` и `8222:8222` на `0.0.0.0` — NATS и монитор слушают ВСЕ интерфейсы VPS (`ss -tlnp` подтвердил). phase1-файл биндит 127.0.0.1, но живой стек поднят с открытым портом | `docker-compose.yml:15-16`; `ss` | подтверждено рантаймом; ufw не проверен (нет sudo) |
| Д3 | ConfirmDialog показывает только заголовок, исполняется provider-controlled `action.subject/name/parameters`; guard — только `subject == COMMANDS_CONTROL` | `app.py:2786` (диалог), `app.py:2887-2898` (исполнение) | подтверждено кодом |
| Д4 | Дормант-сервис `qiki_chat/` слушает `qiki.chat.v1`, маппит текст → `QikiProposedActionV1(dry_run=False)`; в compose не поднят, но это второй командный вход | `qiki_chat/handler.py:78-96` | подтверждено кодом |

Смягчение (честно): сегодня исполняемые действия идут от детерминированной policy —
LLM-путь вырезает actions. Дыры латентны, но Д2+ делает шину доступной извне хоста уже сейчас.

## 3. Архитектура (двухконтурная)

```
Оператор ── RU игровое поле ──→ [F5 ЭКРАН ORION V]  (M1: read-only поверх command mode)
                                     │ intent v2 + auth (M4, M2)
                                     ▼
                              [QIKI GATEWAY] (M3)          ← реальный ключ провайдера ТОЛЬКО тут
                               scope/rate/audit;             виртуальные ключи; audit-only неделя
                                     │
                     ┌───────────────┴────────────────┐
                     ▼ (данные, карантин)             ▼ (control flow, привилегированный)
              [ПРОВАЙДЕР LLM]                  [QIKI POLICY] (детерминированная)
              candidate/reply only                   │ CommandDecision (M5)
              actions стрипаются                     │ validation→publish→ack→effect→audit
                                                     ▼
                                       [ТЕЛО/RUNTIME — УЖЕ ПОСТРОЕНО]
                                       attach / power / thermal / SAFE
                                                     ▼
                                       Telemetry/Audit → F8 улики · F6 журнал · F2 системы
```

Ступени разрешения (propose/commit + human-in-the-loop):
intent → candidate (неисполняемый) → operator approve → `CommandDecision`
(раздельные `validation_state / publish_state / ack_state / effect_state / audit_state`,
идемпотентность по `decision_id`) → только последняя ступень трогает тело.

## 4. Контракты (кандидаты; enum'ы — одним ADR до кода)

- **`QikiChatRequestV2`**: v1 + `auth_context{subject,session,scopes,token_id}`,
  `evidence_context{sensor_trust,source,runtime_claim_status}`, `command_intent_class`,
  `client_claim_level`. v1 совместим через feature-flag.
- **`QikiChatResponseV2`**: v1 + `decision_preview{validation_layers,next_step}`,
  `evidence{source_type,source_id,trust_status,freshness,runtime_claim_status}`.
- **`CommandDecision v1`**: state-machine; **обязан связывать одобренное намерение с ТОЧНЫМ
  публикуемым subject/name/params** (закрывает Д3); RED-тест спуфинга обязателен.
- Словарь-фильтр (из ребейза §5, подтверждён): `seed_only`/`provider_candidate` НЕ вводить;
  `runtime_claim_status`-enum обязан включить живое `local_ui_loop_no_runtime_command`;
  `source_type=provider` — расширение `evidence_claim.py:50` только через ADR+RAG;
  имена стримов согласовать с принятым `PDU_boundary`.

## 5. Интерфейс F5 (DISPLAY_CANON-совместимый; M1 = read-only)

Правила зон: один русский титул, без нижней подписи, T-тест строк, show-when, коды кодами.

```
[F5] QIKI / ДИАЛОГ
╭─ ДИАЛОГ ────────────────────────────────────────────────────────────╮
│ ОПЕРАТОР ▸ 06:00:12Z | доложи состояние                             │
│ QIKI     ▸ 06:00:45Z ACK | состояние стабильное, стыковка активна   │
│ QIKI     ▸ 06:01:32Z REJECT | манёвр отклонён: зона запрета         │
│   └ LEGALITY blocked [zone] ZONE_DENY · TRUST degraded conf=0.62    │  ← коды на строке (тут место есть)
╰─────────────────────────────────────────────────────────────────────╯
╭─ КАНДИДАТ ──────────────────────────────────────────────────────────╮  ← show-when: только когда есть
│ cand-017 | Возобновить наблюдение безопасно | увер. 0.74            │
│ источник: провайдер | candidate_only | НЕ исполняется               │
╰─────────────────────────────────────────────────────────────────────╯
╭─ РЕШЕНИЕ (предпросмотр) ────────────────────────────────────────────╮  ← show-when
│ проверки: доверие → питание → тепло → SAFE | шаг: q approve         │
│ validation: — | publish: — | ack: — | effect: — (не схлопывать!)    │
╰─────────────────────────────────────────────────────────────────────╯
╭─ УЛИКИ ─────────────────────────────────────────────────────────────╮
│ детали: F8 | журнал: F6 | системы: F2                               │
╰─────────────────────────────────────────────────────────────────────╯
  пустое состояние ДИАЛОГА (граница): «QIKI — не внешний чат-бот. Ответ
  провайдера — только кандидат. q: <запрос> — начать диалог.»
```

- Ввод — СУЩЕСТВУЮЩИЙ command mode (`/`, `q:`); M1 не добавляет нового execute-пути
  (gate уровня приложения: тест «добавление F5 не даёт нового пути к `_qiki_pending_action`»).
- Источник ленты — тот же `qiki_voice`-леджер, что в кокпите (№8в): полная глубина (20),
  реплики оператора добавляются из intent-лога. Один владелец данных, ноль новых деривов.
- ACTION RAIL: кнопка «F5 QIKI» добавляется ТОЛЬКО в M1 (вместе с биндингом f5 + LEVEL_META).
  До того слот F5 — резерв в реестре DISPLAY_CANON §4.
- Старая карта ORION OS (F5=Сводка, F9=QIKI) — предыдущее поколение, не наследуется;
  расхождение зафиксировать в реестре при M1.

## 6. Порядок внедрения (строго; каждый M = патч + тесты + live-proof)

| Шаг | Что | Evidence gate |
|---|---|---|
| **H0 (немедленно, вне волн)** | Закрыть внешнюю экспозицию: `docker-compose.yml` порты NATS → `127.0.0.1:4222:4222`, `127.0.0.1:8222:8222`; проверить ufw | `ss` показывает только 127.0.0.1; стек работает |
| **M0a** | Снести secret-по-шине (`qiki.secrets.v1.openai_api_key`): ключ только env/secret-store респондера | `set_key` по шине не меняет env; попытка → deny в аудит |
| **M0b** | `qiki_chat` в карту угроз: retire или gateway-route; в compose не поднимать | контур в `00_CONSOLE_MAP`/threat-doc; `dry_run=False`-путь неактивен |
| **M0c** | allow/deny публикаторов `qiki.responses.qiki` (до внешнего провайдера) | чужой publish → deny (сегодняшний smoke-канал закрывается) |
| **M2** | NATS nkeys/JWT: аккаунты по сервисам; перечислить ВСЕХ клиентов (7 compose + qiki_chat + ~10 тулов) | без JWT подключение падает; весь стек+тулы на credentials |
| **M1** | Экран F5 (read-only, §5) — ПОСЛЕ M2 | нет нового пути к `_qiki_pending_action`; кандидат `candidate_only` |
| **M3** | Gateway: ключ только тут; виртуальные ключи; лимиты (запросы+токены+конкурентность); audit-only неделю; завернуть и q-core→OpenAI трафик | ключ отсутствует в ORION/логах; fail-closed |
| **M4** | Конверт v2 (feature-flag, v1 совместим) | схема-валидация; сквозной request_id |
| **M5** | CommandDecision + DecisionStore; связка намерение↔точная команда | RED-тест спуфинга: benign-заголовок + расходящийся `action.name` НЕ исполняется |
| **M6** | `q approve` → Decision (не execute); блокирующее одобрение | candidate-only/deferred/blocked не достигают шины; approve идемпотентен |
| **M7-M9** | Мост к телу: chat→Decision→`run_attach_pipeline`; power/thermal-предусловия; реплей/экспорт | никакого нового body-кода; JSONL-трасса |

Fail-closed: шлюз упал → F5 read-only; провайдер молчит → структурная ошибка;
предусловия недоступны → deferred/blocked; missing остаётся missing.

## 7. Чего НЕ делать
- НЕ строить заново Face Map/паспорта/физику/PDU (готово, §2.1).
- НЕ развивать legacy-чат (`main_orion.py`).
- НЕ расширять trust/`source_type`/`runtime_claim_status` без ADR+RAG.
- НЕ давать тексту провайдера управлять потоком (CaMeL).
- НЕ добавлять F5-экран до M2 (общий app несёт execute-путь `q confirm`).
- НЕ пересылать ключ провайдера по шине — и снести существующий канал (M0a).

## 8. Открытые вопросы (решения оператора)
1. H0 сейчас? (одна строка compose; требует пересоздания nats-контейнера → рестарт стека).
2. Судьба `qiki_chat/` (M0b): retire или консервировать до gateway?
3. ufw/провайдерский firewall — проверить руками (нужен sudo).
4. ADR на enum'ы `runtime_claim_status`/`source_type` — завести до M4/M5.
5. Строка №9 ACTION RAIL (малая уборка: мёртвые кнопки инцидентов → show-when,
   CMD-подсказка без перечня экранов) — до или параллельно Волне 0.

## 9. Модель угроз и известные ограничения фазы ПРОТОТИПА

Решение оператора 2026-07-05: это **прототип**, не продакшн-дистрибуция.
**Объявленная модель угроз: продюсер ответов (`q_core_intents`) — ДОВЕРЕННЫЙ.**
Обоснование: LLM-actions стрипаются (§2.1), исполнимые действия строит
детерминированная policy в доверенном домене на одном хосте.

При этой модели пломба M5 и гейт M6 — **defense-in-depth против гонок/повторов**,
а не барьер против враждебного продюсера. Adversarial-ревизия 2026-07-05 (три
субагента) подтвердила: если бы продюсер был враждебным, M5/M6/M0c обходились бы
одним крафтовым ответом. Для прототипа с доверенным продюсером это приемлемо.

**Что реально закрыто по «безопасности свободного доступа» (единственный критичный
класс для прототипа):** ВСЕ nats-серверы во всех compose (`docker-compose.yml`,
`phase1.yml`, `minimal.yml`) биндят порты на `127.0.0.1` и требуют `--auth
${NATS_TOKEN}`. Живьём: `ss` на хосте — только 127.0.0.1; gateway:8090 наружу не
проброшен; коннект без токена → `Authorization Violation`.

**Известные ограничения фазы прототипа (приняты сознательно, НЕ баги-сюрпризы):**
- M2 = единый shared-токен, НЕ per-service nkeys/JWT (нет per-service отзыва).
- M0c/M6 полагаются на request_id-членство и provider-supplied `legality.status` —
  достаточно при доверенном продюсере, обходятся co-tenant при враждебном.
- **M5 закрывает пост-seal подмену, НЕ полную Д3**: оператору в ConfirmDialog
  показывается только `title_ru`, не `subject/name/params`. Ложь «безобидный
  заголовок ↔ опасная команда» в ИСХОДНОМ ответе не ловится. Геймплейный долг
  (см. ниже), не security-блокер прототипа.
- **M7-M9 мост `bridge_decision_to_body` протестирован ИЗОЛИРОВАННО**, в живой путь
  консоли к телу НЕ подключён (живой путь — `controller.run_attach_pipeline` на
  локальном снапшоте, клавиша `b`). «Решение проведено к телу» относится к
  библиотеке+smoke, не к продовому контуру.
- `neural_engine.py` держит прямой путь к реальному ключу; контейнмент через
  gateway обеспечен только env-обвязкой `phase1.yml` (не структурно).
- legacy `main_orion.py` не удалён (soft env-guard `ALLOW_LEGACY_OPERATOR_CONSOLE`).

**Геймплейный долг (не security, но суть игры «доверие оператора к боту»):**
показывать оператору РЕАЛЬНУЮ команду (subject/name/params), а не только
заголовок; при желании — подключить мост M7-M9 к живому пути. Приоритет — по
решению оператора, отдельно от security.
