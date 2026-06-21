# QIKI Body v0.2.2 — Инженерное обоснование

## 0. Назначение документа

Этот документ фиксирует инженерное обоснование ключевых решений QIKI Body v0.2.2.

Он объясняет, почему канон тела QIKI вводит жёсткие ограничения и запрещает мягкие фантастические формулировки без цены, evidence и расчётного следа.

Документ не вводит новый канон тела.

Документ не добавляет новые технологии, модули, лорные расширения или runtime-фичи.

Документ не утверждает, что текущий runtime уже реализует описанные решения.

Его задача — защитить QIKI Body v0.2.2 от обратного размягчения: от превращения RTG в вечную батарейку, реактора в обычный модуль на грань, NBL в широкополосную связь, защитного поля в абсолютный щит, field drive в baseline, байонета в магнитную защёлку, RCS в “равномерную тягу без расчёта”, а модуля — в бонус без физической цены.

Главная формула:

Инженерное обоснование не убивает фантазию.

Инженерное обоснование запрещает бесплатную фантазию.

Если технология сильная, она должна быть дорогой.

Если технология нарушает baseline, она должна быть явно помечена.

Если технология влияет на тело, она должна быть видна в расчётах, ORION, command gating, audit и blackbox.

---

## 1. Статус документа

Файл:

`05_ENGINEERING_RATIONALE.md`

Версия:

`v0.2.2`

Статус:

`engineering rationale / documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`01_BODY_CANON.md`

Related source files:

`00_INDEX.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`04_CALCULATION_FRAME.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

`10_READER_MANUAL.md`

---

## 2. Что этот документ объясняет

Этот документ объясняет следующие решения:

почему QIKI является машинным телом, а не голосом модели;

почему батарея и supercap разделены;

почему RTG-class source не является boost-source;

почему reactor-class source не является обычным face-mounted module;

почему NBL является emergency low-rate channel, а не wideband comms;

почему защита не является absolute shield;

почему field drive не является baseline;

почему bayonet требует mechanical hard lock;

почему RCS требует Thrust Map и Torque Map;

почему module passport является обязательным;

почему ACK не равен effect confirmation;

почему ORION является evidence station, а не decorative HUD;

почему первый repository patch должен быть documentation-only.

---

## 3. Что этот документ не делает

Этот документ не рассчитывает точные массы.

Не рассчитывает центр масс.

Не рассчитывает inertia matrix.

Не рассчитывает Thrust Map.

Не рассчитывает Torque Map.

Не задаёт точные thermal thresholds.

Не задаёт точную эффективность защиты.

Не задаёт точный NBL bitrate.

Не задаёт реальные proto / NATS / gRPC contracts.

Не меняет telemetry paths.

Не меняет ORION UI.

Не утверждает implemented.

Не утверждает verified.

Если значение неизвестно, оно должно оставаться `TBD` или `calculation-required`.

---

## 4. Принцип инженерной честности

QIKI Body v0.2.2 строится вокруг простого правила: сильная возможность должна иметь физическую цену.

Цена может выражаться через:

массу;

центр масс;

инерцию;

энергию;

пиковую мощность;

SoC_cap;

тепло;

расход рабочего тела;

cooldown;

сигнатуру;

EMCON-риск;

деградацию сенсоров;

ограничение связи;

ограничение манёвров;

риск отказа;

SAFE-блокировку;

reason_codes;

audit / blackbox relevance.

Если возможность ничего не стоит, она ломает тело QIKI.

Если модуль даёт только преимущества и не создаёт новых ограничений, он не является полноценным модулем QIKI.

Если технология звучит как удобная магия, её нужно либо отклонить, либо пометить как Terta-exotic, либо дать ей цену, блокировки и evidence path.

---

## 5. Иерархия инженерных источников

Для QIKI Body v0.2.2 действует следующая иерархия.

Первый уровень — runtime truth.

Это состояние симуляции, телеметрия, события, ACK, effect confirmation, audit и blackbox.

Второй уровень — внутренний канон пакета.

Это `01_BODY_CANON.md`, `02_REQUIREMENTS.md`, `04_CALCULATION_FRAME.md`, `06_INTERFACE_CONTROL.md` и `07_ADR/`.

Третий уровень — инженерные внешние ориентиры.

Это практики системной инженерии, космической энергетики, тепла, тяги, стыковки, интерфейсов, верификации и документации.

Четвёртый уровень — игровое допущение.

Это допустимое упрощение ради игры, если оно не притворяется реализованной инженерией.

Пятый уровень — Terta-exotic.

Это экзотика Сектора Терта, которая не должна притворяться современным baseline.

Запрещено смешивать уровни.

Нельзя ссылаться на внешний источник как на доказательство того, чего он не подтверждает.

Нельзя переносить Terta-exotic в MVP без маркировки.

Нельзя делать runtime-эффект только потому, что он красиво звучит в тексте.

---

## 6. Почему QIKI является машинным телом

Главный риск проекта — превратить QIKI в голосовую оболочку языковой модели.

В таком варианте модель может звучать убедительно, но физическая причинность исчезнет. Модуль будет “активен” потому, что модель сказала. Команда будет “выполнена” потому, что голос QIKI сообщил об этом. ORION покажет красивый экран, но под ним не будет telemetry source, ACK, effect confirmation, audit и blackbox.

Такой подход разрушает QIKI как проект.

QIKI должна быть машинным телом.

Это значит:

тело имеет состояние;

состояние должно быть проверяемым;

физическое утверждение требует source;

команда требует lifecycle;

эффект требует confirmation;

модуль требует паспорт;

интерфейс требует states и reason_codes;

ORION показывает evidence, а не придумывает реальность.

Модель может объяснять, сомневаться и предлагать.

Модель не подтверждает физический факт.

---

## 7. Почему батарея и supercap разделены

Простая игровая модель могла бы иметь одну шкалу энергии.

Это удобно, но для QIKI неверно.

Если батарея и supercap смешаны, появляется ложная логика: “батарея заряжена, значит QIKI может выполнить boost, high-power scan, NBL packet или active field”.

Для машинного тела это плохая модель.

Батарея отвечает за длительность жизни.

Supercap отвечает за краткий пик.

PDU отвечает за разрешение нагрузки.

Thermal nodes отвечают за физический предел.

SAFE может запретить действие даже при наличии энергии.

Правильная логика:

SoC_bat показывает запас жизни.

SoC_cap показывает готовность к быстрым действиям.

Высокий SoC_bat и низкий SoC_cap означают: QIKI жива, но не готова к резкому пиковому действию.

Запрещённая формулировка:

`Battery 80%, boost available.`

Правильная формулировка:

`Boost requires SoC_cap, PDU allowance, thermal clearance, RCS availability and SAFE clearance.`

Последствия для канона:

одна общая шкала energy запрещена для серьёзных решений;

пиковые команды должны проверять SoC_cap;

ORION должен показывать battery и supercap отдельно;

reason_codes должны объяснять, что именно блокирует пик.

---

## 8. Почему RTG не является boost-source

RTG-class source нельзя описывать как маленькую вечную батарейку.

Корректная роль RTG-class source в QIKI Body v0.2.2:

heavy / trickle source;

долгий источник малой или средней базовой мощности;

источник постоянного тепла;

источник для survival, drift, cold-zone, sleep, slow recharge;

не источник быстрых пиков.

RTG не должен питать:

boost;

NBL-stream;

постоянный high-power scan;

active field как штатный режим;

любые безлимитные пиковые действия.

RTG не должен отменять:

battery;

supercap;

PDU;

thermal model;

cooldown;

signature;

mass / CoM / inertia.

Если RTG сделать обычным модулем на грань, он сломает масштаб QIKI. Малое тело получит ложное ощущение почти бесконечной энергии без серьёзной цены.

Допустимые роли:

внешний тяжёлый пристыкованный модуль;

advanced / heavy mission module;

Terta-derived miniaturized trickle source, если явно помечен и имеет цену.

Запрещённые формулировки:

`RTG battery`;

`RTG boost`;

`RTG solves power`;

`infinite energy`;

`small RTG face module`, если он не помечен как speculative / Terta-exotic и не имеет цены.

Правильная формулировка:

`RTG-class source is a heavy / trickle source, not a boost-source.`

---

## 9. Почему reactor-class source не является face module

Reactor-class source не должен быть обычным модулем, который ставится на грань QIKI.

Реакторный источник высокого класса означает:

большую инфраструктурную цену;

тепло;

массу;

защиту;

радиационный контур;

механические ограничения;

энергетический bridge;

safety;

audit relevance;

ограничение манёвров.

Если reactor-class source превратить в обычный face-mounted upgrade, QIKI перестанет быть малым телом с ограничениями. Она станет платформой, на которую можно повесить почти любую мощность без инженерной цены.

Каноническая роль:

external / station / sled / heavy infrastructure.

QIKI может быть подключена к reactor-class source только через проверенный внешний контур:

structural-rated connection;

electrical safety;

thermal clearance;

power bridge;

passport validation;

PDU allowance;

motion restrictions.

Запрещённые формулировки:

`reactor module on F08`;

`reactor upgrade`;

`normal reactor bayonet module`;

`reactor directly powers all loads`;

`reactor removes power limits`.

Правильная формулировка:

`Reactor-class source is external / station / sled / heavy infrastructure, not a normal face-mounted QIKI module.`

---

## 10. Почему NBL не является wideband comms

NBL в baseline не должен быть каналом обычной связи.

Если NBL сделать широкополосным каналом через всё, он уничтожит часть драматургии и инженерной логики связи:

обычная связь потеряет значение;

EMCON потеряет значение;

задержки и потери канала потеряют значение;

аварийные сообщения станут бесплатными;

изоляция QIKI станет фальшивой;

оператор получит “магический интернет”.

Корректная baseline-роль NBL:

emergency low-rate channel;

короткие критические пакеты;

ограниченная частота;

дорогая передача;

SoC_cap cost;

thermal cost;

PDU gating;

criticality gating;

audit;

blackbox relevance.

NBL должен использоваться не для удобства, а для критического события.

Запрещённые формулировки:

`NBL broadband`;

`NBL normal telemetry`;

`NBL data stream`;

`NBL video`;

`NBL internet through everything`;

`NBL bulk telemetry`.

Правильная формулировка:

`Baseline NBL is emergency low-rate only.`

Если нужен развитый NBL, он должен быть помечен как Terta-exotic и получить цену.

---

## 11. Почему защита не является absolute shield

Защита QIKI не должна быть магическим щитом.

Если защита является абсолютной, исчезают:

риск;

геометрия;

ориентация;

масса;

энергия;

тепло;

сенсорные конфликты;

манёвренность;

деградация;

тактический выбор.

Корректная модель защиты:

частичное снижение конкретного риска;

конкретная геометрия;

конкретный класс угрозы;

конкретная цена;

ограничение действия;

ограничение сенсоров;

тепловой и энергетический след;

reason_codes;

evidence.

Radiation deflector / deployable deflector может быть допустимым механизмом, если он не описан как абсолютный пузырь.

Он может защищать от части угроз, но должен иметь:

массу;

энергию;

тепло;

геометрию;

ограничение ориентации;

конфликт с сенсорами;

конфликт со связью;

конфликт с EMCON;

cooldown;

failure modes.

Запрещённые формулировки:

`absolute shield`;

`full protection`;

`invulnerable field`;

`shield absorbs everything`;

`protection without cost`.

Правильная формулировка:

`Protection is a constrained mechanism against a specific threat class, not an absolute shield.`

---

## 12. Почему field drive не является baseline

Field drive не должен быть baseline-системой движения QIKI.

Baseline-движение QIKI должно опираться на физически ограниченную двигательную логику: RCS, рабочее тело, импульсы, ограничение тяги, тепло, расход, центр масс, инерцию и проверку команд.

Если field drive сделать baseline, появляется опасная формулировка “движение от чистой энергии”. Это стирает рабочее тело, тяговые карты, RCS-геометрию, ограничения по массе, thermal model и смысл манёвров.

Field drive может существовать только как:

Terta-exotic;

advanced speculative;

scenario-specific anomaly;

explicit-cost technology.

Он должен иметь:

энергетическую цену;

тепловую цену;

сигнатуру;

ограничение duty-cycle;

cooldown;

риски;

командный допуск;

evidence path;

audit / blackbox relevance.

Запрещённые формулировки:

`field drive baseline`;

`pure energy thrust`;

`reactionless normal drive`;

`drive without cost`;

`free acceleration`.

Правильная формулировка:

`Field drive is not baseline. If used, it is Terta-exotic and must have explicit cost, limits and evidence path.`

---

## 13. Почему bayonet требует mechanical hard lock

Байонет не должен держаться на магнитном замке как на основном силовом элементе.

Магнит может помогать выравниванию.

Магнит может быть частью pre-align.

Магнит может помогать soft capture.

Но магнит не должен считаться structural lock.

Байонет является механическим, энергетическим, информационным и каскадным интерфейсом. Через него могут идти питание, данные, внешний модуль, механическая нагрузка и bridge state. Поэтому он требует строгой последовательности состояний.

Каноническая цепочка:

approach;

alignment;

magnetic pre-align;

soft capture;

mechanical hard lock;

structural check;

electrical safety;

umbilical mate;

module handshake;

passport validation;

bridge allowed.

Почему это важно:

soft capture не выдерживает все нагрузки;

bridge без electrical safety опасен;

модуль без passport validation не должен быть runtime-ready;

aggressive burn при bridge active опасен;

emergency detach должен быть отдельным состоянием;

audit должен видеть state transition.

Запрещённые формулировки:

`magnetic lock as structural lock`;

`soft capture allows power bridge`;

`bridge active after contact`;

`bayonet connected means module ready`.

Правильная формулировка:

`Bayonet requires mechanical hard lock, structural check, electrical safety, module handshake and passport validation before bridge allowed.`

---

## 14. Почему RCS требует Thrust Map и Torque Map

RCS нельзя объявлять равномерной и управляемой без расчёта.

QIKI имеет многогранное тело, RCS-кластеры, модули, байонеты, возможные внешние блоки и смещающийся центр масс. Поэтому тяга и момент не могут быть честно описаны фразой “RCS работает”.

Нужны:

Thrust Map;

Torque Map;

положения сопел;

направления тяги;

плечи сил;

остаточные моменты;

остаточные линейные компоненты;

зоны plume-clearance;

зависимость от CoM_delta;

зависимость от inertia_class;

зависимость от working mass;

зависимость от thermal nodes;

ограничения bayonet / bridge.

Без этих карт нельзя честно утверждать:

balanced thrust;

full attitude control;

safe docking burn;

tumble recovery;

aggressive burn;

uniform translation;

all-axis authority.

Запрещённые формулировки:

`RCS is isotropic`;

`RCS has balanced thrust`;

`full maneuverability`;

`manual thruster control as normal gameplay`;

`all-axis control verified`, если нет карты.

Правильная формулировка:

`RCS requires Thrust Map and Torque Map before balanced thrust or full control can be claimed.`

---

## 15. Почему module passport обязателен

Модуль без паспорта не является runtime-модулем.

Название модуля ничего не доказывает.

Если написано “radiation shield”, “sensor boom”, “reactor block”, “NBL transmitter”, “field drive”, “extra tank” или “compute module”, это ещё не означает, что модуль существует в теле QIKI.

Паспорт модуля нужен, чтобы модуль имел:

mount point;

массу;

позицию;

CoM impact;

inertia impact;

power profile;

thermal node;

capabilities;

costs;

blocked commands;

new commands;

failure modes;

degradation modes;

SAFE interactions;

sensor effects;

comms effects;

RCS effects;

bayonet effects;

telemetry fields;

reason_codes;

audit requirements;

blackbox relevance;

status.

Без паспорта модуль является идеей, лорной заготовкой или визуальным элементом.

Он не должен быть runtime-ready.

Запрещённые формулировки:

`module installed`, если нет mount point;

`module active`, если нет power / thermal / state;

`module gives capability`, если нет cost;

`module runtime-ready`, если нет passport;

`module implemented`, если нет evidence.

Правильная формулировка:

`Module passport is mandatory for runtime-ready module status.`

---

## 16. Почему ACK не равен effect confirmation

ACK — это подтверждение, что команда принята, доставлена или обработана нижним слоем.

ACK не означает, что физический эффект произошёл.

Если RCS controller дал ACK, это не доказывает изменение скорости или ориентации.

Если PDU дал ACK, это не доказывает стабильную подачу мощности.

Если bayonet module дал ACK, это не доказывает, что hard lock выдержал нагрузку.

Если comms channel дал ACK, это не доказывает, что адресат получил и понял полезную информацию.

Для QIKI принципиально различать:

request;

validation;

allowed / rejected;

publish;

ACK;

effect confirmation;

audit.

Почему это важно:

иначе команда превращается в магию;

ORION начнёт показывать выполненное действие без эффекта;

postmortem будет читать ложные логи;

оператор перестанет понимать, где цепь оборвалась.

Запрещённые формулировки:

`ACK means complete`;

`command accepted means effect happened`;

`published means executed`;

`allowed means done`.

Правильная формулировка:

`ACK is not effect confirmation.`

---

## 17. Почему ORION является evidence station

ORION не должен быть декоративным HUD.

Если ORION просто красиво рисует состояние, он может стать источником интерфейсной лжи.

Для QIKI ORION должен быть evidence station.

Он должен показывать:

source;

freshness;

trust;

status;

reason_codes;

target-only;

not implemented;

calculation-required;

ACK;

effect confirmation;

audit trail;

blackbox relevance.

ORION может упрощать, группировать и подсвечивать информацию, но не должен выдумывать физику.

Если данных нет, нужно показывать missing / unknown.

Если данные устарели, нужно показывать stale.

Если есть конфликт, нужно показывать conflicting.

Если функция целевая, но не реализованная, нужно показывать target-only / not implemented.

Запрещённые формулировки:

`ORION shows truth`, если нет source;

`UI confirms effect`, если нет effect confirmation;

`panel active means module active`;

`green indicator means verified`.

Правильная формулировка:

`ORION is an evidence station, not a decorative HUD.`

---

## 18. Почему первый patch должен быть documentation-only

QIKI Body v0.2.2 сначала должен войти в проект как документационный пакет.

Если сразу менять runtime-код, proto, NATS, gRPC, telemetry paths или ORION UI, будут смешаны три разных состояния:

канон описан;

расчётный каркас задан;

runtime реализован.

Эти состояния нельзя смешивать.

Документ может сказать, что должно быть.

Таблица может сказать, где должны жить значения.

Interface record может сказать, как должен выглядеть обмен.

ADR может сказать, почему принято решение.

Но это не implementation.

Первый patch должен:

создать markdown files;

создать ADR files;

добавить local index;

добавить acceptance checks;

добавить alignment note к старому GDD;

не менять runtime;

не менять generated files;

не писать implemented без evidence.

Запрещённые формулировки:

`runtime now supports QIKI Body v0.2.2`;

`implemented by documentation`;

`tests prove behavior`, если тестов нет;

`telemetry supports`, если telemetry path не проверен.

Правильная формулировка:

`First repository patch is documentation-only. Runtime work requires a separate task and evidence.`

---

## 19. Forbidden wording table

| Запрещённая формулировка | Правильная замена |
|---|---|
| RTG battery | RTG-class heavy / trickle source |
| RTG boost | RTG cannot be boost-source |
| Reactor module on face | Reactor-class external / station / sled source |
| NBL broadband | NBL emergency low-rate only |
| NBL telemetry stream | NBL critical packet only |
| Absolute shield | constrained protection / deflector |
| Field drive baseline | field drive Terta-exotic / not baseline |
| Magnetic lock | magnetic pre-align / mechanical hard lock required |
| Soft capture connected | soft capture is not bridge allowed |
| RCS balanced | RCS requires Thrust Map and Torque Map |
| Module installed | module installed only with mount point and passport |
| Module active | module active only with state, power, thermal evidence |
| ACK complete | ACK is not effect confirmation |
| ORION truth | ORION evidence view with source |
| Target-only implemented | target-only is not runtime-ready |
| Template is schema | template-only is not runtime schema |
| Table is calculation | table is not calculated unless values are verified |

---

## 20. Связь с ADR

Этот документ объясняет rationale.

ADR фиксирует решения.

Если одно из решений нужно изменить, нельзя просто переписать этот документ задним числом.

Нужно создать новый ADR или supersede существующий.

Минимальный набор связанных ADR:

`ADR-0001-machine-body-not-model-voice.md`

`ADR-0002-body-canon-separated-from-old-gdd.md`

`ADR-0003-battery-supercap-split.md`

`ADR-0004-rtg-trickle-not-boost.md`

`ADR-0005-reactor-external-source.md`

`ADR-0006-nbl-emergency-low-rate.md`

`ADR-0007-deflector-not-absolute-shield.md`

`ADR-0008-field-drive-not-baseline.md`

`ADR-0009-bayonet-mechanical-hard-lock.md`

`ADR-0010-rcs-thrust-torque-maps-required.md`

`ADR-0011-module-passport-mandatory.md`

`ADR-0012-documentation-only-first-patch.md`

`ADR-0013-reader-manual-derived.md`

`ADR-0014-orion-evidence-station.md`

`ADR-0015-ack-not-effect-confirmation.md`

---

## 21. Acceptance for this document

`05_ENGINEERING_RATIONALE.md` считается готовым для documentation-only package, если:

объяснено, почему QIKI является машинным телом;

объяснено разделение battery / supercap;

объяснено, почему RTG не boost-source;

объяснено, почему reactor external / station / sled;

объяснено, почему NBL emergency low-rate;

объяснено, почему protection not absolute shield;

объяснено, почему field drive not baseline;

объяснено, почему bayonet hard lock required;

объяснено, почему RCS requires maps;

объяснено, почему module passport mandatory;

объяснено, почему ACK is not effect confirmation;

объяснено, почему ORION evidence station;

объяснено, почему first patch documentation-only;

есть forbidden wording table;

нет новых технологий;

нет invented numbers;

нет implemented claims;

нет verified claims без evidence;

нет runtime conformance claims.

---

## 22. Итоговая формула

QIKI Body v0.2.2 не запрещает фантастику.

Он запрещает бесплатную фантастику.

Сильная технология должна иметь цену.

Опасное утверждение должно иметь evidence.

Модуль должен иметь паспорт.

Команда должна иметь lifecycle.

ACK не должен подменять эффект.

ORION не должен подменять реальность.

Reader manual не должен подменять source files.

Documentation patch не должен подменять runtime implementation.

Это инженерная дисциплина, которая удерживает QIKI как машинное тело.
