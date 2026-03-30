# Решение Проблемы IDE Import Issues

## Проблема
IDE/LSP показывает ошибки импортов для generated Protocol Buffers классов, но код работает в runtime через sys.path.append().

## Причина
- **IDE анализирует** статические пути импортов
- **Python runtime** использует динамическое разрешение через sys.path

## Решения (на выбор)

### Вариант 1: Добавить .pth файл (Рекомендуемый)
```bash
cd /home/sonra44/QIKI_DTMP
echo "$PWD" > qiki.pth
# Поместить qiki.pth в site-packages или использовать PYTHONPATH
```

### Вариант 2: Настроить IDE
**For VS Code:**
```json
// .vscode/settings.json
{
    "python.analysis.extraPaths": ["/home/sonra44/QIKI_DTMP"],
    "python.defaultInterpreterPath": "/usr/bin/python3"
}
```

**For PyCharm:**
- Settings → Project → Python Interpreter → Show All → Show paths
- Add `/home/sonra44/QIKI_DTMP`

### Вариант 3: Использовать относительные импорты
Изменить импорты в services на:
```python
# Вместо:
from generated.bios_status_pb2 import BiosStatusReport

# Использовать:
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from generated.bios_status_pb2 import BiosStatusReport
```

### Вариант 4: __init__.py файлы
Создать __init__.py в root директории:
```bash
touch /home/sonra44/QIKI_DTMP/__init__.py
```

## Статус
⚠️ Не критично для функционирования - система работает стабильно
✅ Рекомендуется Вариант 1 для лучшего IDE experience