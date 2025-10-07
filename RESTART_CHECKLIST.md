# Чек-лист действий после перезагрузки

## 1. Проверка установленных компонентов
```powershell
# Запустить PowerShell от имени администратора и проверить:
python --version        # Должно быть 3.12.x
node --version         # Должно быть 23.11.1
java --version         # Должно быть OpenJDK 21
docker --version       # Должно быть 28.4.x
```

## 2. Настройка Firewall (запускать от админа)
```powershell
# Для Grafana
New-NetFirewallRule -DisplayName "QIKI-Grafana" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow

# Для NATS
New-NetFirewallRule -DisplayName "QIKI-NATS" -Direction Inbound -Protocol TCP -LocalPort 4222 -Action Allow
New-NetFirewallRule -DisplayName "QIKI-NATS-HTTP" -Direction Inbound -Protocol TCP -LocalPort 8222 -Action Allow

# Для Loki
New-NetFirewallRule -DisplayName "QIKI-Loki" -Direction Inbound -Protocol TCP -LocalPort 3100 -Action Allow
```

## 3. Установка глобальных NPM пакетов
```powershell
# Установка глобальных пакетов
npm install -g @charmland/crush@0.7.4 @google/gemini-cli@0.6.1 @openai/codex@0.42.0 @qwen-code/qwen-code@0.0.12
```

## 4. Проверка Python пакетов
```powershell
# Проверка основных пакетов
python -c "import grpc; print(f'gRPC {grpc.__version__}')"
python -c "import faststream; print(f'FastStream {faststream.__version__}')"
python -c "import pydantic; print(f'Pydantic {pydantic.__version__}')"
pytest --version
ruff --version
mypy --version
```

## 5. Проверка Docker
```powershell
# Проверка Docker и Docker Compose
docker ps
docker compose version
```

## 6. Настройка Docker Desktop
- [ ] CPUs: 4+ ядра
- [ ] Memory: 8GB+ (рекомендуется 12GB)
- [ ] Disk image size: 100GB+
- [ ] Use Docker Compose V2: ✅

## После выполнения всех проверок
- [ ] Убедиться, что все компоненты установлены и работают
- [ ] Проверить что все порты свободны и доступны
- [ ] Убедиться что Docker Desktop корректно настроен

## Следующие шаги:
1. Запуск проекта через docker-compose
2. Проверка работоспособности всех сервисов
3. Запуск тестов для подтверждения корректной работы