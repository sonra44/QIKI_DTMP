"""
Модуль загрузки и управления конфигурацией qiki-docgen.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class QikiDocgenConfig:
    """Управление конфигурацией qiki-docgen."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path
        self._config_data = {}
        self._project_root = self._find_project_root()
        self._load_config()
    
    def _find_project_root(self) -> Path:
        """Находит корневую директорию проекта."""
        current_dir = Path(__file__).parent.parent.parent.parent  # Поднимаемся к QIKI_DTMP
        
        # Проверяем наличие характерных файлов проекта
        markers = ['protos', 'services', 'docs', 'README.md']
        
        for marker in markers:
            if (current_dir / marker).exists():
                return current_dir
        
        # Fallback - текущая директория
        logger.warning("Не удалось найти корень проекта, использую текущую директорию")
        return Path.cwd()
    
    def _load_config(self):
        """Загружает конфигурацию из YAML файла."""
        if not self.config_path:
            # Ищем config.yaml рядом с этим модулем
            config_dir = Path(__file__).parent.parent
            self.config_path = config_dir / "config.yaml"
        
        if not self.config_path.exists():
            logger.warning(f"Конфигурационный файл не найден: {self.config_path}")
            self._config_data = self._get_default_config()
            return
        
        try:
            content = self.config_path.read_text(encoding='utf-8')
            self._config_data = self._parse_yaml(content)
            logger.info(f"Конфигурация загружена из: {self.config_path}")
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            self._config_data = self._get_default_config()
    
    def _parse_yaml(self, content: str) -> Dict[str, Any]:
        """Простой YAML парсер для конфигурации."""
        config = {}
        current_section = None
        current_dict = config
        
        for line in content.split('\n'):
            line = line.rstrip()
            
            # Пропускаем комментарии и пустые строки
            if not line or line.strip().startswith('#'):
                continue
            
            # Определяем уровень вложенности
            indent_level = len(line) - len(line.lstrip())
            line = line.strip()
            
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if indent_level == 0:
                    # Корневой уровень
                    if not value:
                        # Секция
                        current_section = key
                        config[key] = {}
                        current_dict = config[key]
                    else:
                        # Простое значение
                        config[key] = self._parse_value(value)
                elif indent_level == 2 and current_section:
                    # Вложенный уровень
                    if not value:
                        # Подсекция
                        current_dict[key] = {}
                    else:
                        current_dict[key] = self._parse_value(value)
                elif indent_level == 4 and current_section:
                    # Глубоко вложенный уровень (для списков)
                    if key.startswith('- '):
                        # Элемент списка
                        list_key = key[2:]  # Убираем "- "
                        if isinstance(current_dict, dict):
                            # Создаем список если его нет
                            last_key = list(current_dict.keys())[-1] if current_dict else None
                            if last_key and not isinstance(current_dict[last_key], list):
                                current_dict[last_key] = []
                            if last_key:
                                current_dict[last_key].append(self._parse_value(list_key))
                    else:
                        current_dict[key] = self._parse_value(value)
        
        return config
    
    def _parse_value(self, value: str) -> Any:
        """Парсит значение в правильный тип."""
        if not value:
            return None
        
        # Boolean значения
        if value.lower() in ('true', 'yes', 'on'):
            return True
        if value.lower() in ('false', 'no', 'off'):
            return False
        
        # Числа
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Убираем кавычки
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        
        return value
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию по умолчанию."""
        return {
            'paths': {
                'protos_dir': 'protos',
                'generated_dir': 'generated',
                'docs_dir': 'docs',
                'design_dir': 'docs/design',
                'templates_dir': 'tools/qiki_docgen/templates',
                'protoc_includes': [
                    '/usr/include',
                    '/data/data/com.termux/files/usr/include',
                    '/opt/homebrew/include'
                ]
            },
            'protoc': {
                'python_flags': ['--python_out'],
                'options': {
                    'generate_pyi': False,
                    'package_relative': True
                }
            },
            'generation': {
                'default_template': 'default',
                'available_templates': ['default', 'minimal', 'advanced']
            },
            'logging': {
                'level': 'INFO'
            }
        }
    
    def get_path(self, path_key: str) -> Path:
        """Получает абсолютный путь для указанного ключа."""
        relative_path = self._config_data.get('paths', {}).get(path_key, '')
        if not relative_path:
            raise ValueError(f"Путь '{path_key}' не найден в конфигурации")
        
        return self._project_root / relative_path
    
    def get_protoc_includes(self) -> List[str]:
        """Получает список include путей для protoc."""
        includes = self._config_data.get('paths', {}).get('protoc_includes', [])
        
        # Фильтруем только существующие пути
        existing_includes = []
        for include_path in includes:
            if Path(include_path).exists():
                existing_includes.append(include_path)
        
        if not existing_includes:
            logger.warning("Не найдено ни одного существующего include пути для protoc")
        else:
            logger.info(f"Найдены include пути: {existing_includes}")
        
        return existing_includes
    
    def get(self, key: str, default=None) -> Any:
        """Получает значение конфигурации по ключу."""
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

# Глобальная инстанция конфигурации
_config_instance = None

def get_config() -> QikiDocgenConfig:
    """Получает глобальную инстанцию конфигурации."""
    global _config_instance
    if _config_instance is None:
        _config_instance = QikiDocgenConfig()
    return _config_instance