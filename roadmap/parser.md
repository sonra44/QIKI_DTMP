СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  

---

### Вход и цель  
[Факт] Модуль парсинга `.proto` и `design.md`.  
Цель — разобраться в извлечении структуры.

### Сбор контекста  
[Факт] Использует `Path`, `re`, стандартные коллекции.  
[Гипотеза] Предназначен для построения README и метаданных.

### Локализация артефакта  
`tools/qiki_docgen/core/parser.py`; импортируется в генератор.

### Фактический разбор  
- Класс `ProtoParser`: извлекает package, messages, enums, services.  
- Класс `DesignDocParser`: обрабатывает frontmatter, секции, metadata.

### Роль в системе и связи  
[Факт] Поставщик структурированных данных для генератора.  
[Гипотеза] Может использоваться автономно для анализа репо.

### Несоответствия и риски  
- [Факт] Регулярные выражения без защиты от вложенных блоков — **Med**.  
- [Факт] Невалидация YAML frontmatter — **Low**.  
- [Гипотеза] Ограничение на 5 строк комментария — **Low**.

### Мини-патчи  
- [Патч] Ограничить `re.finditer` по времени или глубине.  
- [Патч] Добавить try/except для `_extract_sections`.

### Рефактор-скетч  
```python
@dataclass
class ProtoMessage:
    name: str
    fields: list[Field]
    description: str = ""
```

### Примеры использования  
```python
# 1. Парсинг proto
ProtoParser().parse_proto_file(Path("sample.proto"))
# 2. Парсинг design.md
DesignDocParser().parse_design_doc(Path("docs/foo.md"))
# 3. Получение только messages
parser = ProtoParser(); parser.parse_proto_file(p)["messages"]
# 4. Проверка наличия frontmatter
DesignDocParser().parse_design_doc(p)["has_frontmatter"]
# 5. Вручную извлечь секции
DesignDocParser()._extract_sections(text)
```

### Тест‑хуки/чек‑лист  
- Proto с вложенными message/enum.  
- Design без frontmatter.  
- Ошибочный YAML.  
- Наличие комментариев перед блоками.  
- Unicode в именах.

### Вывод  
1. Парсер покрывает основные сущности.  
2. Регулярки могут ломаться на сложных файлах.  
3. Желательно использовать protobuf‑компилятор для AST.  
4. Для design.md — рассмотреть PyYAML.  
5. Сократить дублирование кода.  
6. Добавить типы (TypedDict/dataclass).  
7. Улучшить логирование уровней.  
8. Написать интеграционные тесты.  
9. Проверить поддержку Windows путей.  
10. Рефактор после стабилизации требований.

---

СПИСОК ФАЙЛОВ  
1. QIKI_DTMP/tools/qiki_docgen/core/generator.py  
2. QIKI_DTMP/tools/qiki_docgen/core/parser.py  
3. QIKI_DTMP/tools/qiki_docgen/requirements.txt  
4. QIKI_DTMP/tools/qiki_docgen/templates/advanced_component.proto.template  
5. QIKI_DTMP/tools/qiki_docgen/templates/advanced_design.md.template  
