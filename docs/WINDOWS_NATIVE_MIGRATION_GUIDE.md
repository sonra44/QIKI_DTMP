# МИГРАЦИЯ НА WINDOWS 11 - НАТИВНАЯ УСТАНОВКА

**Дата**: $(date)
**Подход**: Только нативные Windows инструменты + Docker Desktop
**Без**: WSL2, виртуальных машин, Linux подсистем

---

## 🎯 СТРАТЕГИЯ МИГРАЦИИ

### Ключевые принципы:
1. ✅ **Docker Desktop для Windows** - основа всей системы
2. ✅ **Python for Windows** - нативная установка
3. ✅ **Node.js for Windows** - нативная установка  
4. ✅ **Git for Windows** - система контроля версий
5. ❌ **НЕТ WSL2** - работаем напрямую в Windows
6. ❌ **НЕТ виртуальных окружений** - все через Docker

---

## 📊 ЧТО УСТАНОВИТЬ НА WINDOWS 11

### 1. Docker Desktop for Windows (КРИТИЧЕСКИ ВАЖНО)
```powershell
# Скачать с: https://docs.docker.com/desktop/windows/install/
# Версия: Docker Desktop 4.x+
# Требования: Windows 11 Pro/Enterprise (для Hyper-V)

# Настройки после установки:
# Settings → General → Use Docker Compose V2 ✅
# Settings → Resources → Advanced:
#   - CPUs: 4+
#   - Memory: 8GB минимум (лучше 12GB)
#   - Disk image size: 100GB+
```

### 2. Python 3.12 for Windows
```powershell
# Скачать с: https://www.python.org/downloads/windows/
# Версия: Python 3.12.x (точно как на сервере)
# При установке:
# ✅ Add Python to PATH
# ✅ Install pip
# ✅ Install for all users

# Проверка после установки:
python --version
pip --version
```

### 3. Node.js for Windows
```powershell
# Скачать с: https://nodejs.org/
# Версия: 23.11.1 (точно как на сервере)
# Или через Chocolatey:
choco install nodejs --version=23.11.1

# Проверка:
node --version  # должно быть v23.11.1
npm --version
```

### 4. Git for Windows
```powershell
# Скачать с: https://git-scm.com/download/win
# Или через Chocolatey:
choco install git

# Проверка:
git --version
```

### 5. OpenJDK 21 for Windows
```powershell
# Скачать Microsoft Build OpenJDK 21:
# https://docs.microsoft.com/java/openjdk/download

# Или через Chocolatey:
choco install openjdk21

# Проверка:
java --version
```

### 6. Chocolatey (опционально, для удобства)
```powershell
# В PowerShell как администратор:
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

### 7. Visual Studio Code (опционально)
```powershell
# Скачать с: https://code.visualstudio.com/
# Расширения: Docker, Python, Git
```

---

## 📦 PYTHON ПАКЕТЫ - ГЛОБАЛЬНАЯ УСТАНОВКА

Поскольку работаем без venv, устанавливаем все глобально:

### Основные зависимости
```cmd
# В Command Prompt или PowerShell:

# Обновление pip
python -m pip install --upgrade pip

# gRPC инфраструктура (КРИТИЧЕСКИ ВАЖНО!)
pip install grpcio>=1.62.0
pip install grpcio-tools>=1.62.0
pip install protobuf>=4.21.0

# FastStream + NATS (КЛЮЧЕВЫЕ для системы!)
pip install "faststream[nats]>=0.5.0"
pip install "faststream[cli]>=0.5.0"
pip install nats-py>=2.6.0

# Базовые зависимости
pip install "pydantic>=2.0.0"
pip install "pydantic[email]>=2.0.0"
pip install "PyYAML>=6.0"
pip install colorlog
pip install setuptools

# Мониторинг
pip install prometheus-client>=0.20.0

# Инструменты разработки
pip install pytest>=8.2
pip install pytest-cov>=5.0
pip install pytest-asyncio
pip install ruff>=0.6.9
pip install mypy>=1.11.1
pip install psutil>=5.9.0

# Веб-сервер (для FastStream)
pip install uvicorn>=0.23.0
```

### NPM пакеты (глобальные)
```cmd
# Глобальная установка (из анализа сервера):
npm install -g @charmland/crush@0.7.4
npm install -g @google/gemini-cli@0.6.1
npm install -g @openai/codex@0.42.0
npm install -g @qwen-code/qwen-code@0.0.12
```

---

## 📁 СТРУКТУРА ПРОЕКТА НА WINDOWS

### Рекомендуемое расположение
```
C:\Projects\
├── QIKI_DTMP\              # Главный проект
│   ├── docker-compose.phase1.yml
│   ├── Dockerfile.dev
│   ├── src\
│   ├── config\
│   └── ...
└── NOVA\                   # Вспомогательный проект
    ├── docker-compose.yml
    └── Dockerfile
```

### Команды копирования с сервера
```cmd
# Вариант 1: SCP (если установлен Git Bash)
scp -r user@server:/home/sonra44/QIKI_DTMP/ C:\Projects\
scp -r user@server:/home/sonra44/NOVA/ C:\Projects\

# Вариант 2: Через Git (если есть репозиторий)
cd C:\Projects
git clone <repository-url> QIKI_DTMP

# Вариант 3: Архив
# На сервере: tar -czf project.tar.gz QIKI_DTMP/ NOVA/
# На Windows: распаковать в C:\Projects\
```

---

## 🐳 АДАПТАЦИЯ DOCKER COMPOSE ДЛЯ WINDOWS

### Проблема: Linux пути в docker-compose
Нужно изменить volume mappings в `docker-compose.phase1.yml`:

```yaml
# БЫЛО (Linux):
volumes:
  - .:/workspace
  - pip-cache-phase1:/root/.cache/pip

# СТАЛО (Windows):
volumes:
  - .:/workspace
  - pip-cache-phase1:/root/.cache/pip
  # Windows пути работают автоматически через Docker Desktop
```

### Проблема: Line endings (CRLF vs LF)
```cmd
# В Git Bash или через Git настройки:
git config --global core.autocrlf false
git config --global core.eol lf

# Конвертация файлов:
dos2unix docker-compose.phase1.yml  # если есть dos2unix
# Или в VS Code: View → Command Palette → "Change End of Line Sequence" → LF
```

---

## 🚀 ПОШАГОВЫЙ ЗАПУСК

### Шаг 1: Проверка окружения
```cmd
# Проверяем все установленные компоненты:
docker --version
docker-compose --version
python --version
node --version
java --version
git --version

# Проверяем Python пакеты:
python -c "import grpc; print('gRPC OK')"
python -c "import faststream; print('FastStream OK')"
python -c "import nats; print('NATS OK')"
```

### Шаг 2: Подготовка проекта
```cmd
cd C:\Projects\QIKI_DTMP

# Проверяем структуру:
dir
type docker-compose.phase1.yml

# Проверяем права (Windows обычно не проблема):
# Dockerfile должны иметь правильные line endings
```

### Шаг 3: Сборка образов
```cmd
cd C:\Projects\QIKI_DTMP

# Сборка всех образов:
docker-compose -f docker-compose.phase1.yml build

# При ошибках - по одному:
docker-compose -f docker-compose.phase1.yml build nats
docker-compose -f docker-compose.phase1.yml build qiki-dev
# и так далее
```

### Шаг 4: Первый запуск
```cmd
# Запуск системы:
docker-compose -f docker-compose.phase1.yml up -d

# Мониторинг:
docker-compose -f docker-compose.phase1.yml ps
docker-compose -f docker-compose.phase1.yml logs -f
```

### Шаг 5: Проверка работоспособности
```cmd
# NATS healthcheck:
curl http://localhost:8222/healthz
# Или в браузере: http://localhost:8222/healthz

# Grafana:
# Браузер: http://localhost:3000

# Loki:
curl http://localhost:3100/ready
# Или в браузере: http://localhost:3100/ready
```

---

## 🚨 WINDOWS-СПЕЦИФИЧНЫЕ ПРОБЛЕМЫ

### Проблема 1: Docker Desktop не запускается
```powershell
# Включить Hyper-V:
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All

# Включить контейнеры Windows:
Enable-WindowsOptionalFeature -Online -FeatureName Containers

# Перезагрузка системы обязательна!
```

### Проблема 2: Порты заняты
```cmd
# Проверка портов:
netstat -ano | findstr :3000
netstat -ano | findstr :4222
netstat -ano | findstr :8222

# Завершение процессов:
taskkill /PID <PID> /F
```

### Проблема 3: Firewall блокирует порты
```powershell
# В PowerShell как администратор:
New-NetFirewallRule -DisplayName "QIKI-Grafana" -Direction Inbound -Port 3000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "QIKI-NATS" -Direction Inbound -Port 4222 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "QIKI-NATS-HTTP" -Direction Inbound -Port 8222 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "QIKI-Loki" -Direction Inbound -Port 3100 -Protocol TCP -Action Allow
```

### Проблема 4: Python пакеты не находятся
```cmd
# Проверяем PATH:
echo %PATH%

# Переустановка проблемных пакетов:
pip uninstall grpcio grpcio-tools
pip install grpcio grpcio-tools --no-cache-dir

# Проверка установки:
pip list | findstr grpc
pip list | findstr faststream
```

### Проблема 5: Line endings в скриптах
```cmd
# В Git Bash (если доступен):
find . -name "*.py" -exec dos2unix {} \;
find . -name "*.yml" -exec dos2unix {} \;

# Или через PowerShell:
Get-ChildItem -Recurse -Include *.py,*.yml | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content -replace "`r`n", "`n"
    Set-Content $_.FullName $content -NoNewline
}
```

---

## 📋 ОТЛИЧИЯ ОТ LINUX ВЕРСИИ

### Что остается ТАК ЖЕ:
- ✅ Docker Compose конфигурация
- ✅ NATS JetStream настройки
- ✅ gRPC протоколы
- ✅ FastStream логика
- ✅ Python код в контейнерах

### Что МЕНЯЕТСЯ:
- 🔄 Пути к файлам (Windows style, но Docker обрабатывает)
- 🔄 Line endings (LF вместо CRLF)
- 🔄 Права доступа (Windows не так критичен)
- 🔄 Сетевые интерфейсы (localhost через Docker Desktop)
- 🔄 Переменные окружения PATH

### Что ДОБАВЛЯЕТСЯ:
- ➕ Windows Firewall правила
- ➕ Hyper-V включение
- ➕ Docker Desktop специфические настройки
- ➕ PowerShell скрипты для управления

---

## 🛠️ ПОЛЕЗНЫЕ КОМАНДЫ ДЛЯ WINDOWS

### Docker управление
```cmd
# Статус системы:
docker-compose -f docker-compose.phase1.yml ps

# Перезапуск сервиса:
docker-compose -f docker-compose.phase1.yml restart nats

# Логи:
docker-compose -f docker-compose.phase1.yml logs nats
docker-compose -f docker-compose.phase1.yml logs qiki-dev

# Остановка:
docker-compose -f docker-compose.phase1.yml down

# Очистка:
docker system prune -a
```

### Мониторинг ресурсов
```cmd
# Память и CPU:
tasklist /FI "IMAGENAME eq Docker Desktop.exe"
wmic process where name="Docker Desktop.exe" get PageFileUsage,WorkingSetSize

# Docker статистика:
docker stats
```

### Сетевая диагностика
```cmd
# Проверка портов:
telnet localhost 4222
telnet localhost 8222

# HTTP тесты:
curl http://localhost:8222/healthz
curl http://localhost:3100/ready

# Ping контейнеров:
docker exec -it qiki-nats-phase1 ping google.com
```

---

## ✅ ЧЕКЛИСТ УСПЕШНОЙ МИГРАЦИИ

### Подготовка Windows
- [ ] Windows 11 Pro/Enterprise
- [ ] Hyper-V включен
- [ ] Docker Desktop установлен и запущен
- [ ] Docker Desktop настроен (8GB+ RAM, 4+ CPU)

### Инструменты
- [ ] Python 3.12.x установлен глобально
- [ ] Node.js 23.11.1 установлен
- [ ] OpenJDK 21 установлен
- [ ] Git for Windows установлен

### Python пакеты  
- [ ] grpcio, grpcio-tools установлены
- [ ] faststream[nats] установлен
- [ ] nats-py установлен
- [ ] Все остальные зависимости установлены
- [ ] Нет ошибок import при проверке

### Проект
- [ ] Файлы QIKI_DTMP скопированы в C:\Projects\
- [ ] Line endings исправлены (LF)
- [ ] Docker образы собираются без ошибок
- [ ] docker-compose.phase1.yml запускается

### Сеть и безопасность
- [ ] Firewall правила для портов 3000,3100,4222,8222
- [ ] Порты свободны (не заняты другими приложениями)
- [ ] Antivirus не блокирует Docker

### Функциональность
- [ ] NATS отвечает на /healthz
- [ ] Grafana доступна на :3000
- [ ] Loki доступна на :3100
- [ ] Все контейнеры в статусе running/healthy

---

## 🎯 ЗАКЛЮЧЕНИЕ

**Возможность нативной миграции на Windows 11: ВЫСОКАЯ ✅**

Благодаря тому что:
1. **Вся логика в Docker контейнерах** - не зависит от хост-системы
2. **Docker Desktop для Windows** обеспечивает полную совместимость Linux контейнеров
3. **Python/Node.js/Java** имеют качественные Windows версии
4. **NATS, gRPC, FastStream** - кроссплатформенные технологии

**Критические факторы успеха:**
- Правильная настройка Docker Desktop (достаточно ресурсов)
- Корректная установка всех Python зависимостей глобально
- Исправление line endings в конфигурационных файлах
- Настройка Windows Firewall для нужных портов

**Итоговое время работы:** После правильной настройки система должна работать **идентично** серверу Ubuntu, поскольку все микросервисы выполняются в Linux контейнерах внутри Docker Desktop.

---
