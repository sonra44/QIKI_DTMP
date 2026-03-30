# RE_QIKI_Runtime_Evidence_Notes

> REFERENCE ONLY / NOT CURRENT STATUS
>
> CURRENT TRUTH OVERRIDE:
> current project status must be read from:
> - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
> - `TASKS/TASK_20260330_qiki_freshness_threshold_ownership.md`
> - `TASK_OUT/final_stabilization_and_baseline.md`
>
> Historical package-state below may be stale. In particular, references to
> `G3-QIKI-009`, `proof-stage`, or `signature_changed live path` unresolved are
> retained as historical evidence-control context, not as current active-slice truth.

## 1. Назначение

Этот документ фиксирует **не общую архитектурную уверенность**, а именно границу между:

- тем, что уже подтверждено кодом, контрактами и конфигурационным устройством проекта;
- тем, что подтверждено только частично;
- тем, что всё ещё требует отдельной live/runtime-проверки.

Его задача — не допускать подмены формулы
`architecture recovered`
формулой
`runtime fully verified`.

---

## 2. Текущая честная формула состояния

```text
architecture_confidence = high
contract_confidence = high
runtime_proof_confidence = partial
documentation_confidence = high
active_slice = proof-stage
main_blocker = signature_changed live path
closure = not yet
```

Это означает:

- проект хорошо восстановлен как система;
- активный срез уже описан и привязан к рабочему контуру;
- но финальное закрытие текущего этапа всё ещё нельзя объявлять.

---

## 3. Active slice

**Текущий active slice:** `G3-QIKI-009`

**Текущий статус:** `proof-stage`

Это корректно читать так:

- slice не гипотетический;
- slice встроен в общую архитектурную картину;
- slice опирается на реальный кодовой и контрактный контур;
- но его нельзя переводить в `closed`, пока не снят главный runtime blocker.

---

## 4. Что уже можно считать подтверждённым

## 4.1. Подтверждён архитектурный spine проекта

На уровне кода и собранного пакета уже подтверждён рабочий хребет системы:

```text
spec stack
  -> WorldModel / q_sim_service
  -> contracts / events / telemetry / radar
  -> faststream_bridge + q_core_agent
  -> ORION V
  -> registrar / audit trail
```

Это означает, что базовая карта проекта держится не на гипотезе, а на устойчиво читаемом кодовом контуре.

## 4.2. Подтверждён spec stack, но не как один файл-owner

Подтверждено, что machine/runtime specification задаётся не одним источником, а стеком:

```text
spec_stack
  = env/config selection
  + bot_config.json
  + root config/*
  + service-level config
```

Следовательно, корректно считать подтверждённым именно **spec stack**, а не сводить ownership всей спецификации к одному файлу.

## 4.3. Подтверждён physical/runtime truth spine

На текущем уровне можно считать подтверждённым, что:

- `WorldModel` и `q_sim_service` формируют physical/runtime truth spine;
- transport и event-контур публикуют состояние и события;
- operator и audit-слои не должны объявляться владельцами физической истины.

Это уже достаточно сильное основание для core-документов.

## 4.4. Подтверждён contract / subject spine

В проекте устойчиво читается реальный контрактный и subject-слой:

- telemetry subjects;
- radar subjects;
- command / response channels;
- intents channels;
- `qiki.events.v1.*`;
- audit channels.

Это означает, что transport surface описан не абстрактно, а через реальные семейства событий и обмена.

## 4.5. Подтверждён статус ORION V как primary operator surface

На текущем этапе ORION V можно считать подтверждённой основной операторской поверхностью проекта.

Это **не** означает, что остальные entrypoints исчезли.
Это означает, что при чтении пакета именно ORION V должен удерживаться как primary operator surface.

## 4.6. Подтверждён audit trail, но не как single-owner truth

Подтверждено, что audit-layer реально существует и собирает значимый след событий.

Но корректная формула здесь такая:

```text
audit_layer
  = registrar as collector / republisher
  + direct audit publishers in active services
```

Следовательно, подтверждён именно audit trail как слой, но не монолитный `audit owner = registrar only`.

## 4.7. Подтверждён BIOS-related runtime contour

Подтверждено, что BIOS-логика в проекте реальна, но распределена между несколькими частями:

- `q_bios_service`;
- BIOS-handling внутри `q_core_agent`;
- config-driven ожиданиями и состояниями.

Это означает, что BIOS path подтверждён как активный support/runtime contour, но ещё не является идеально упрощённым single-owner слоем.

---

## 5. Что подтверждено только частично

## 5.1. Decision layer как живой контур

`q_core_agent` подтверждён как canonical decision layer.

Но live-proof по всей decision цепочке остаётся частичным.

Корректная формула:

- decision architecture recovered — да;
- decision role understood — да;
- full end-to-end runtime proof — ещё нет.

## 5.2. Intents path / ownership

Подтверждено, что intents проходят через реальный рабочий contour.

Но окончательный owner нельзя считать финально закрытым без оговорок.

Корректнее так:

```text
operator intent path
  = compose-dependent
  = faststream_bridge path OR q_core_intents path
```

Следовательно, подтверждён сам рабочий контур intents, но ownership по нему остаётся частично незакрытым.

## 5.3. Product-critical slice как рабочий сценарий

Текущий продуктовый срез уже читается как часть реального ядра проекта.

Но на текущем этапе это означает только следующее:

- slice структурно и продуктово понятен;
- slice не является случайной веткой;
- slice ещё нельзя объявлять полностью доказанным live-сценарием.

---

## 6. Что остаётся незакрытым

## 6.1. Главный runtime blocker

**Незакрытый элемент:** `signature_changed live path`

**Статус:** `unresolved`

Пока этот путь не подтверждён на правильном runtime-контуре, active slice нельзя честно переводить в `closed`.

Это главный незакрытый доказательный элемент текущего этапа.

## 6.2. Compose / environment state

Дополнительная незакрытая зона — подтверждение того, что runtime stack поднят на корректном контуре и проверка выполняется в релевантной среде.

Пока это не подтверждено, сохраняется риск делать выводы поверх неполной или неактуальной operational-state картины.

---

## 7. Что нельзя утверждать на текущем этапе

Сейчас нельзя корректно утверждать, что:

- active slice полностью закрыт;
- `signature_changed` подтверждён;
- все критические runtime paths verified end-to-end;
- пакет можно переводить в final closure только на основании архитектурной ясности;
- ownership по intents уже финально и безусловно определён.

---

## 8. Что должно изменить статус evidence

Чтобы усилить статус текущего evidence-слоя, требуется:

1. поднять и перепроверить runtime/compose contour;
2. проверить live path для `signature_changed`;
3. зафиксировать наблюдение как отдельный evidence update;
4. обновить maturity matrix;
5. после этого пересинхронизировать core-docs.

До этого момента корректный статус остаётся таким:

- active slice = `proof-stage`
- runtime proof = `partial`
- main blocker = `signature_changed live path`

---

## 9. Итоговая формула

```text
QIKI current evidence state:
  architecture = strongly recovered
  spec stack = confirmed as layered
  runtime spine = confirmed
  contracts = confirmed
  operator surface = ORION V primary
  audit layer = confirmed but non-monolithic
  BIOS contour = confirmed but mixed
  decision layer = confirmed
  intents ownership = partially unresolved
  runtime proof = still partial
  active slice = proof-stage
  closure = not yet
```

---

## 10. Статус документа

**Тип:** evidence-control document  
**Роль:** удерживает границу между доказанным и ещё не доказанным  
**Правило обновления:** изменяется только после реального evidence-update, а не после общей аналитической интерпретации
