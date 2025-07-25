# Руководство по Ручной Настройке Окружения

Этот документ описывает шаги, которые необходимо выполнить вручную один раз для подготовки рабочего окружения Termux к работе над проектом QIKI_DTMP.

## 1. Обновление Пакетов Termux

```bash
pkg update -y && pkg upgrade -y
```

## 2. Установка Основных Зависимостей

Нам понадобятся `python`, `curl` и `unzip`.

```bash
pkg install python curl unzip -y
```

## 3. Установка Компилятора Protobuf (`protoc`)

Из-за несовместимости стандартных пакетов, мы устанавливаем `protoc` вручную из официального репозитория GitHub.

```bash
# 1. Скачиваем архив
curl -LO https://github.com/protocolbuffers/protobuf/releases/download/v25.3/protoc-25.3-linux-aarch_64.zip

# 2. Распаковываем бинарные файлы в системную директорию
unzip -o protoc-25.3-linux-aarch_64.zip -d /data/data/com.termux/files/usr

# 3. Удаляем архив
rm protoc-25.3-linux-aarch_64.zip

# 4. Проверяем установку
protoc --version
```

После выполнения этих шагов, окружение будет полностью готово к использованию инструмента `qiki-docgen` и дальнейшей разработке.
