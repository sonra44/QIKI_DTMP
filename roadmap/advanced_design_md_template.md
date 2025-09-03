СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  

---

### Вход и цель  
[Факт] Jinja2‑шаблон для расширенного дизайн‑документа.  
Цель — оценить структуру и полноту разделов.

### Сбор контекста  
[Факт] YAML frontmatter, множество секций (Executive Summary, API, Deployment…).  
[Гипотеза] Используется как скелет для архитектурных документов.

### Локализация артефакта  
`tools/qiki_docgen/templates/advanced_design.md.template`; применяется `create_design_document`.

### Фактический разбор  
- Frontmatter: `component_name`, `version`, `author`, `status`, `tags`.  
- 15 разделов, включающие бизнес‑контекст, тестирование, риски, changelog.  
- Кодовые примеры: Mermaid диаграмма, SQL, YAML.

### Роль в системе и связи  
[Факт] Входной шаблон для проектной документации.  
[Гипотеза] Служит стандартом для команды разработки.

### Несоответствия и риски  
- [Факт] Жестко прошитые даты (`2025‑08‑05`) — **Med**.  
- [Факт] Нет ссылок на реальный ADR/API путь — **Low**.  
- [Гипотеза] Документ может быть слишком громоздким для MVP — **Low**.

### Мини-патчи  
- [Патч] Использовать `created_at|default(now())`.  
- [Патч] Добавить placeholder для ревью даты.

### Рефактор-скетч  
```markdown
---
component_name: {{ component_name }}
created_at: {{ created_at | default(now()) }}
review_due: {{ review_due | default("") }}
---
```

### Примеры использования  
```bash
# 1. Генерация документа
python -m qiki_docgen.generator create_design_document Foo docs/foo.md --template advanced
# 2. Dry-run
python -m qiki_docgen.generator create_design_document Foo docs/foo.md --dry-run
# 3. Заполнение переменных
jinja2-cli advanced_design.md.template component_name=Bar author="Team"
# 4. Проверка frontmatter
head -n 10 docs/foo.md
# 5. Превращение в PDF
pandoc docs/foo.md -o docs/foo.pdf
```

### Тест‑хуки/чек‑лист  
- Корректность YAML frontmatter.  
- Наличие всех 15 разделов после генерации.  
- Unicode в `component_name`.  
- Валидация списков и таблиц.  
- Проверка ссылки на связанные документы.

### Вывод  
1. Шаблон очень полный, покрывает жизненный цикл.  
2. Дата и автор по умолчанию требуют динамики.  
3. Можно упрощать для легких проектов.  
4. Добавить переменные для review/owner.  
5. Предусмотреть перевод на другие языки.  
6. Хранить пример в тестах для регрессии.  
7. Разделить на модули (API, Deployment) по необходимости.  
8. Встроить ссылки на ADR/API.  
9. Автоматизировать заполнение changelog.  
10. Сначала патч‑фиксы (даты), позже — модульность.

---

СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  
