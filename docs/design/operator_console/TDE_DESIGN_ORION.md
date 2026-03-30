# Дизайн-спецификация: QIKI TUI Shell "ORION" (Terminal Desktop Environment)

> **STATUS NOTE (2026-02-04):** This document is a design snapshot (2025-12-20).  
> It contains valuable UI principles, but its “Sixel-first is verified” framing can be misread as the current canon.
>
> Canon for radar visualization (SSH+tmux reality; multi-backend; mouse+color) is:
> - `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
> - `docs/design/canon/ADR/ADR_2026-02-04_radar_visualization_strategy.md`

**Статус:** Design snapshot (reference; see RFC/ADR for canon decisions)  
**Дата:** 2025-12-20  
**Контекст:** Реализация интерфейса оператора в парадигме "Terminal as a Cockpit" с использованием Textual; bitmap-рендер (Kitty/SIXEL) рассматривается как capability-upgrade, не как обязательное предположение.

---

## 1. Философия и Эстетика

Мы не строим "консольное меню". Мы строим **Терминальную Настольную Среду (TDE)**.

*   **Метафора:** "Стеклянная кабина" (Glass Cockpit) космического корабля Orion/Dragon.
*   **Визуальный язык:**
    *   **Брутализм:** Жесткие двойные рамки (`border: double`), моноширинные шрифты, отсутствие скруглений.
    *   **Высокая плотность:** Максимум информации на квадратный символ. Таблицы, спарклайны, индикаторы.
    *   **Темная тема:** Глубокий черный фон (`#050505`), янтарный (`#FFB000`) или "NASA Green" активный цвет.
*   **Принципы UX:**
    *   **Global Command Bus:** Командная строка всегда доступна и всегда внизу (как Dock).
    *   **MFD (Multi-Function Displays):** Экран разделен на зоны, контент в которых переключается, но каркас остается неизменным.

---

## 2. Технический Стек (Verified)

1.  **Framework:** **Textual** (Python). Единственный выбор для реактивного TUI с CSS-версткой.
2.  **Графическое Ядро:**
    *   **`textual-image`:** Библиотека-обертка, предоставляющая виджет `SixelImage`. Это "правильный вариант" интеграции (Best Practice 2025).
    *   **`Pillow` (PIL) / `Matplotlib`:** Генерация растрового кадра в памяти. Pillow быстрее для простых примитивов (точки, линии радара), Matplotlib проще для сложных графиков. Для радара используем **Pillow** (Draw API) ради производительности.
3.  **Транспорт:** `NATS JetStream` (через `nats-py`).
4.  **Шина данных:** `FastStream Bridge` (уже реализован).

---

## 3. Архитектура: "Micro-Kernel UI"

Текущая реализация (`main.py`) использует `TabbedContent`. Это подходит для утилит, но не для ОС. Новая архитектура строится на **ContentSwitcher**.

### 3.1. Компоновка (Layout)

```text
Screen (Root)
├── Header (Status Bar: Time, Connection, Battery)     [Dock: Top]
├── Body (Grid Layout)                                 [Flexible]
│   ├── Left Sidebar (Navigation/Mode list)            [Width: 20]
│   └── MFD Area (ContentSwitcher)                     [Rest]
│       ├── Screen: System Monitor (Grid)
│       ├── Screen: Radar Sixel View (Full)
│       └── Screen: Comms/Logs (Flow)
└── Command Bus (Input + Log Overlay)                  [Dock: Bottom]
```

### 3.2. Реактивное Хранилище (State Store)

Состояние приложения (`GameState`) выносится из UI-классов в отдельный реактивный синглтон.

```python
from textual.reactive import reactive

class GameState:
    # Физика
    battery_level = reactive(100.0)
    velocity = reactive(0.0)
    
    # Интерфейс
    active_mfd = reactive("system_monitor")
    alert_level = reactive("NORMAL") # NORMAL, CAUTION, WARNING
    
    # Данные радара (храним сырой объект, рендер отдельно)
    latest_radar_frame = reactive(None)
```

---

## 4. Реализация Sixel-Радара (Verified Approach)

Используем `textual-image` для рендеринга и `Pillow` для рисования.

### 4.1. Виджет `SixelRadarDisplay`

```python
import io
from textual.widgets import Static
from textual_image.widgets import SixelImage  # The Verified Library
from PIL import Image, ImageDraw

class SixelRadarDisplay(Static):
    def update_frame(self, radar_data):
        # 1. Создаем Canvas в памяти (Pillow) - RGBA for transparency
        img = Image.new('RGBA', (800, 600), color=(0, 0, 0, 0)) 
        draw = ImageDraw.Draw(img)
        
        # 2. Рисуем сетку и цели (используя данные NATS)
        self._draw_grid(draw)
        self._draw_blips(draw, radar_data)
        
        # 3. Конвертируем в байты (SixelImage сам сделает encode)
        # Это ключевое отличие от ручного python-sixel
        self.query_one(SixelImage).update(img)
```

**Оптимизация:** Обновлять картинку не чаще 5-10 раз в секунду, иначе терминал захлебнется потоком Sixel-данных.

---

## 5. Структура Проекта (Refactoring)

```text
src/qiki/services/operator_console/
├── main.py                 # Entrypoint (App Class)
├── config.py               # CSS переменные и настройки
├── core/
│   ├── state.py            # Reactive GameState
│   └── loop.py             # Simulation Loop (Тикер)
├── clients/
│   └── nats_adapter.py     # NATS -> GameState updater
├── ui/
│   ├── app.tcss            # Глобальные стили (NASA theme)
│   ├── shell.py            # Основной Layout (Header, Dock, Switcher)
│   └── screens/
│       ├── mfd_system.py   # Экран системы (Grid с прогресс-барами)
│       ├── mfd_radar.py    # Экран радара (Sixel Widget)
│       └── mfd_comms.py    # Экран логов
└── widgets/
    ├── command_bus.py      # Input виджет с логикой парсинга
    ├── retro_bar.py        # Кастомный прогресс-бар (сегментированный)
    └── sixel_canvas.py     # Обертка над SixelImage
```

---

## 6. План Миграции

1.  **Phase 0 (Cleanup):** Удалить лишние `main_*.py`, создать структуру папок.
2.  **Phase 1 (Shell):** Реализовать `main.py` с `Command Bus` и `ContentSwitcher` (пока пустые экраны). Проверить работу докинга ввода.
3.  **Phase 2 (Sixel Core):** Интегрировать `textual-image`. Создать тестовый виджет, который рисует статичную картинку. Убедиться, что терминал (Warp/iTerm/Alacritty) это "ест".
4.  **Phase 3 (Data Binding):** Подключить NATS. Связать `telemetry` топик с `GameState`.
5.  **Phase 4 (Radar):** Реализовать отрисовку точек радара через Pillow -> SixelImage.
