СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  

---

### Вход и цель  
[Факт] Шаблон расширенного Proto контракта.  
Цель — описать структуру и риски.

### Сбор контекста  
[Факт] Использует Jinja2‑переменные `component_name`, `component_proto_type`.  
[Гипотеза] Для крупного enterprise‑компонента.

### Локализация артефакта  
`tools/qiki_docgen/templates/advanced_component.proto.template`; компилируется `protoc`.

### Фактический разбор  
- Message `{{ component_proto_type }}`, `Configuration`, `ResourceLimits`, `HealthStatus`, `Metrics`.  
- Services с CRUD, batch, search, streaming.  
- Большой набор enums и вспомогательных типов.

### Роль в системе и связи  
[Факт] Служит базовым шаблоном для новых компонент.  
[Гипотеза] Применяется при `create_proto_contract`.

### Несоответствия и риски  
- [Факт] Не указан пакет `common_types.proto` источник — **Med**.  
- [Факт] Нет опции customize по feature flags — **Low**.  
- [Гипотеза] Шаблон может быть избыточным для маленьких сервисов — **Low**.

### Мини-патчи  
- [Патч] Указать `syntax = "proto3";` в начале (есть).  
- [Патч] Добавить комментарии по optional/required.

### Рефактор-скетч  
```proto
message {{ component_proto_type }} {
  qiki.common.UUID id = 1;
  string name = 2;
  // ...
  optional Configuration config = 13;
}
```

### Примеры использования  
```bash
# 1. Генерация файла
python -m qiki_docgen.generator create_proto_contract Foo --template advanced
# 2. Компиляция
protoc -I=. --python_out=. foo.proto
# 3. Проверка enum
grep "EntityStatus" foo.proto
# 4. Смена имени
python -m qiki_docgen.generator create_proto_contract Bar --dry-run
# 5. Использование в gRPC
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. foo.proto
```

### Тест‑хуки/чек‑лист  
- Прогон `protoc` на сгенерированном файле.  
- Проверка импорта `common_types.proto`.  
- Генерация Python и TypeScript кодов.  
- Тест на отсутствующие поля в CRUD запросах.  
- Соответствие имен service и messages.

### Вывод  
1. Шаблон богат функционалом.  
2. Требует внешних зависимостей (`common_types.proto`).  
3. Избыточен для простых сервисов.  
4. Нужна документация по настройкам.  
5. Возможны конфликты имен.  
6. Стоит параметризовать включаемые секции.  
7. Проверить совместимость с gRPC‑Gateway.  
8. Добавить опцию отключения health/metrics.  
9. Прописать версии пакета.  
10. Рефактор: разнести на части, подключать по флагам.

---

СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  
