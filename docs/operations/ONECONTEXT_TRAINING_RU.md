# ONECONTEXT: Практическое обучение (RU)

Дата: 2026-02-22

## Цель
Научиться использовать OneContext без шума и пропусков: от быстрого поиска до точного доказательства в контенте.

## Шаг 0. Проверка готовности (обязательно)
```bash
scripts/onecontext_safe.sh watcher status
scripts/onecontext_safe.sh worker status
```

Критерий:
1. `Watcher Status: Running`
2. `Worker: Running`

Если `Worker: Stopped`:
```bash
scripts/onecontext_safe.sh worker start
```

Важно: для стабильного `-t content` в ограниченных средах всегда используем wrapper,
он автоматически выставляет `SQLITE_TMPDIR=/tmp`.

## Шаг 1. Снимок контекста
```bash
scripts/onecontext_safe.sh context show
```

Зачем: понять активный контекст и список сессий.

## Шаг 2. Широкий поиск только по turn/session
Пример (тема Docker):
```bash
scripts/onecontext_safe.sh search "docker|compose|mount|workflow" -t turn --count
scripts/onecontext_safe.sh search "docker|compose|mount|workflow" -t turn --from 0 --to 8
```

Зачем: быстро найти релевантные turn без тяжелого шума из raw content.

## Шаг 3. Отбор turn_id
Из результата шага 2 берете нужный `turn` (например: `4225d912-...`).

## Шаг 4. Точечный deep-dive по контенту
```bash
scripts/onecontext_safe.sh search "docker|compose|mount" -t content --turns 4225d912 --from 0 --to 6 --snippet-context 80
```

Зачем: получить доказательство только из выбранного turn, а не из всей истории.

## Шаг 5. Пагинация (если много совпадений)
```bash
scripts/onecontext_safe.sh search "docker|compose|mount" -t content --turns 4225d912 --from 6 --to 12 --snippet-context 80
```

Правило: двигаем окно `--from/--to`, не расширяем поиск «везде».

## Шаг 6. Как формировать итог для себя
1. Короткий ответ (1-2 предложения).
2. 2-4 факта из найденных turn.
3. 1-2 целевых сниппета из `-t content --turns ...` как доказательство.

## Частые ошибки и жесткие правила
1. Ошибка: сразу делать глобальный `-t content`.
   Правильно: сначала `-t turn`, потом `-t content --turns ...`.
2. Ошибка: работать при остановленном `worker`.
   Правильно: сначала health-check.
3. Ошибка: читать все подряд без окон.
   Правильно: фиксированные окна `--from/--to`.

## Быстрый минимальный сценарий (копировать и выполнять)
```bash
scripts/onecontext_safe.sh watcher status
scripts/onecontext_safe.sh worker status
scripts/onecontext_safe.sh context show
scripts/onecontext_safe.sh search "docker|compose|mount|workflow" -t turn --count
scripts/onecontext_safe.sh search "docker|compose|mount|workflow" -t turn --from 0 --to 8
scripts/onecontext_safe.sh search "docker|compose|mount" -t content --turns 4225d912 --from 0 --to 6 --snippet-context 80
```
