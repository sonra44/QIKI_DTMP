СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  

---

### Вход и цель  
[Факт] Анализируем модуль генерации документации и Proto‑контрактов.  
Цель — обзор возможностей и потенциальных улучшений.

### Сбор контекста  
[Факт] Используются `Jinja2`, `subprocess`, `shutil`, парсеры из `parser.py` и конфигурация `config.py`.  
[Гипотеза] Модуль задуман как CLI‑утилита в составе doc‑генератора.

### Локализация артефакта  
`tools/qiki_docgen/core/generator.py`; Python 3.11+, запускается как библиотека/скрипт.

### Фактический разбор  
- `to_snake_case`, `create_design_document`, `create_proto_contract`, `compile_protos`, `build_readme`.  
- Сбор путей из конфигурации, работа с Jinja‑шаблонами, запуск `protoc`.

### Роль в системе и связи  
[Факт] Центральная точка генерации артефактов; зависит от `parser.py` и конфигурации.  
[Гипотеза] Встраивается в CI/CD для автоматизации документации.

### Несоответствия и риски  
- [Факт] Нет проверки существования шаблонов — **Med**.  
- [Факт] `compile_protos` удаляет `generated_dir` без бэкапа — **Med**.  
- [Гипотеза] Ошибки не пробрасываются вверх в `create_*` — **Low**.

### Мини-патчи  
- [Патч] Проверять `template` перед рендерингом.  
- [Патч] В `compile_protos` использовать `exist_ok=True` при создании каталога.

### Рефактор-скетч  
```python
def safe_render(template_name, **ctx):
    env = _get_jinja_env()
    if template_name not in env.list_templates():
        raise FileNotFoundError(template_name)
    return env.get_template(template_name).render(**ctx)
```

### Примеры использования  
```bash
# 1. Создание design.md
python -m qiki_docgen.generator create_design_document Foo docs/Foo_design.md
# 2. Создание proto
python -m qiki_docgen.generator create_proto_contract Foo
# 3. Dry‑run README
python -m qiki_docgen.generator build_readme --dry-run
# 4. Компиляция proto
python -m qiki_docgen.generator compile_protos
# 5. Смена шаблона
python -m qiki_docgen.generator create_design_document Bar docs/Bar.md --template advanced
```

### Тест‑хуки/чек‑лист  
- Unit: `to_snake_case` (разные кейсы).  
- Интеграция: `create_proto_contract` + проверка файла.  
- Негативные: отсутствие `protoc`.  
- Проверка dry‑run режимов.  
- README собирается без шаблонов.

### Вывод  
1. Модуль зрелый, но требует валидаций.  
2. Добавить проверки существования шаблонов.  
3. Защитить удаление `generated_dir`.  
4. Расширить логирование ошибок.  
5. Вынести общие утилиты в отдельный модуль.  
6. Настроить покрытие тестами.  
7. Документировать CLI параметры.  
8. Рассмотреть async для I/O операций.  
9. Подумать о конфигурируемом логгере.  
10. План: патч‑фиксы сейчас, рефактор позже.

---

СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  
