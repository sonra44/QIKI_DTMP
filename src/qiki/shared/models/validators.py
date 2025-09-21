"""
Пользовательские валидаторы для Pydantic моделей QIKI DTMP.
Для сложной или переиспользуемой логики валидации.
Версия: 1.0
Дата: 2025-08-19
"""

import re


# Пример пользовательского валидатора (можно добавить по необходимости)
def is_valid_entity_id(value: str) -> bool:
    """Проверяет, что ID имеет ожидаемый формат, например 'qiki-core-123'."""
    if not isinstance(value, str):
        return False
    return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", value))
