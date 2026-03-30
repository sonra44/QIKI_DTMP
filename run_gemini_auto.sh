#!/bin/bash

# Скрипт для полностью автономного запуска Gemini
# Подает все необходимые подтверждения автоматически

TASK="АВТОНОМНАЯ ЗАДАЧА:
1. Запусти: timeout 30s ./scripts/run_qiki_demo.sh
2. Анализируй логи в .agent/logs/ 
3. Создай gemini_report.txt с кратким отчетом
4. РАБОТАЙ БЕЗ ПОДТВЕРЖДЕНИЙ!"

# Создаем массив автоответов
AUTO_ANSWERS=(
    "yes"
    "y" 
    "да"
    "continue"
    "proceed"
    "1"
    "run"
    "execute"
    "ok"
    "accept"
    "confirm"
    ""
)

# Создаем временный файл с ответами
ANSWERS_FILE="/tmp/gemini_auto_$(date +%s).txt"
for answer in "${AUTO_ANSWERS[@]}"; do
    echo "$answer" >> "$ANSWERS_FILE"
done

# Запускаем Gemini с подачей ответов
echo "Запускаю Gemini с автоответами..."
timeout 300s gemini -p "$TASK" < "$ANSWERS_FILE" &

GEMINI_PID=$!
echo "Gemini PID: $GEMINI_PID"

# Мониторим процесс
while kill -0 "$GEMINI_PID" 2>/dev/null; do
    echo "Gemini работает... (PID: $GEMINI_PID)"
    sleep 10
done

echo "Gemini завершен"
rm -f "$ANSWERS_FILE"

# Проверяем результат
if [ -f "gemini_report.txt" ]; then
    echo "✅ Отчет создан: gemini_report.txt"
    ls -la gemini_report.txt
else
    echo "❌ Отчет не создан"
fi