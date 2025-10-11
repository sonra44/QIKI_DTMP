"""
Internationalization (i18n) module for QIKI Operator Console.
Supports English and Russian languages.
"""

from typing import Dict, Any, List, Optional


class I18n:
    """Internationalization manager for the operator console."""
    
    def __init__(self, language: str = "en"):
        """
        Initialize i18n with default language.
        
        Args:
            language: Language code ("en" or "ru")
        """
        self.current_language = language.lower()
        self.translations = self._load_translations()
    
    def _load_translations(self) -> Dict[str, Dict[str, Any]]:
        """Load all translations."""
        return {
            "en": {
                "app": {
                    "title": "QIKI Operator Console",
                    "subtitle": "Digital Twin Control Center"
                },
                "buttons": {
                    "start_simulation": "Start Simulation",
                    "stop_simulation": "Stop Simulation",
                    "pause_simulation": "Pause Simulation",
                    "resume_simulation": "Resume Simulation",
                    "reset_simulation": "Reset Simulation",
                    "send_message": "Send Message",
                    "clear_chat": "Clear Chat",
                    "export_data": "Export Data",
                    "diagnostics": "Diagnostics"
                },
                "status": {
                    "connected": "Connected",
                    "disconnected": "Disconnected",
                    "connecting": "Connecting",
                    "error": "Error",
                    "running": "Running",
                    "stopped": "Stopped",
                    "paused": "Paused"
                },
                "panels": {
                    "telemetry": "Telemetry Panel",
                    "simulation": "Simulation Control",
                    "chat": "Agent Chat",
                    "metrics": "System Metrics",
                    "radar": "Radar Contacts",
                    "logs": "System Logs"
                },
                "messages": {
                    "simulation_status": "Simulation {simulation_id} is {status}",
                    "connection_failed": "Failed to connect to {service}",
                    "command_executed": "Command {command} executed successfully",
                    "error_occurred": "Error occurred: {error}"
                },
                "commands": {
                    "start": "Start",
                    "stop": "Stop", 
                    "pause": "Pause",
                    "resume": "Resume",
                    "reset": "Reset",
                    "status": "Status",
                    "help": "Help"
                },
                "metrics": {
                    "cpu_usage": "CPU Usage",
                    "memory_usage": "Memory Usage",
                    "disk_usage": "Disk Usage",
                    "network_rx": "Network RX",
                    "network_tx": "Network TX",
                    "uptime": "Uptime",
                    "connections": "Connections"
                }
            },
            "ru": {
                "app": {
                    "title": "Консоль оператора QIKI",
                    "subtitle": "Центр управления цифровым двойником"
                },
                "buttons": {
                    "start_simulation": "Запустить симуляцию",
                    "stop_simulation": "Остановить симуляцию", 
                    "pause_simulation": "Приостановить симуляцию",
                    "resume_simulation": "Возобновить симуляцию",
                    "reset_simulation": "Сбросить симуляцию",
                    "send_message": "Отправить сообщение",
                    "clear_chat": "Очистить чат",
                    "export_data": "Экспорт данных",
                    "diagnostics": "Диагностика"
                },
                "status": {
                    "connected": "Подключено",
                    "disconnected": "Отключено", 
                    "connecting": "Подключение",
                    "error": "Ошибка",
                    "running": "Работает",
                    "stopped": "Остановлено",
                    "paused": "Приостановлено"
                },
                "panels": {
                    "telemetry": "Панель телеметрии",
                    "simulation": "Управление симуляцией",
                    "chat": "Чат с агентом",
                    "metrics": "Системные метрики",
                    "radar": "Радарные контакты",
                    "logs": "Системные логи"
                },
                "messages": {
                    "simulation_status": "Симуляция {simulation_id} в состоянии {status}",
                    "connection_failed": "Не удалось подключиться к {service}",
                    "command_executed": "Команда {command} выполнена успешно", 
                    "error_occurred": "Произошла ошибка: {error}"
                },
                "commands": {
                    "start": "Старт",
                    "stop": "Стоп",
                    "pause": "Пауза", 
                    "resume": "Продолжить",
                    "reset": "Сброс",
                    "status": "Статус",
                    "help": "Помощь"
                },
                "metrics": {
                    "cpu_usage": "Использование ЦП",
                    "memory_usage": "Использование памяти",
                    "disk_usage": "Использование диска",
                    "network_rx": "Сеть RX",
                    "network_tx": "Сеть TX",
                    "uptime": "Время работы",
                    "connections": "Соединения"
                }
            }
        }
    
    def get_available_languages(self) -> List[str]:
        """Get list of available language codes."""
        return list(self.translations.keys())
    
    def set_language(self, language: str) -> None:
        """
        Set current language.
        
        Args:
            language: Language code ("en" or "ru")
        """
        language = language.lower()
        if language in self.translations:
            self.current_language = language
        else:
            # Fall back to English
            self.current_language = "en"
    
    def translate(self, key: str, **kwargs) -> str:
        """
        Translate a key to current language.
        
        Args:
            key: Translation key (e.g., "app.title")
            **kwargs: Parameters for string formatting
            
        Returns:
            Translated string or key if not found
        """
        try:
            # Navigate nested dictionary structure
            keys = key.split('.')
            value = self.translations[self.current_language]
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    # Key not found, return original key
                    return key
                    
            # If we got here, we found the translation
            if isinstance(value, str):
                return self._format_message(value, **kwargs)
            else:
                # Value is not a string, return key
                return key
                
        except (KeyError, TypeError):
            # Language not found or other error, return key
            return key
    
    def t(self, key: str, **kwargs) -> str:
        """
        Shorthand for translate method.
        
        Args:
            key: Translation key
            **kwargs: Parameters for string formatting
            
        Returns:
            Translated string
        """
        return self.translate(key, **kwargs)
    
    def _format_message(self, message: str, **kwargs) -> str:
        """
        Format message with parameters.
        
        Args:
            message: Message template
            **kwargs: Parameters for formatting
            
        Returns:
            Formatted message
        """
        if not kwargs:
            return message
            
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            # Formatting failed, return original message
            return message


# Global instance
_i18n_instance: Optional[I18n] = None


def get_i18n() -> I18n:
    """Get or create global i18n instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    """
    Global shortcut for translations.
    
    Args:
        key: Translation key
        **kwargs: Parameters for formatting
        
    Returns:
        Translated string
    """
    return get_i18n().translate(key, **kwargs)


def set_language(language: str) -> None:
    """
    Set global language.
    
    Args:
        language: Language code ("en" or "ru")
    """
    get_i18n().set_language(language)


def get_current_language() -> str:
    """Get current global language."""
    return get_i18n().current_language