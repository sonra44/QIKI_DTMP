"""
Internationalization (i18n) module for QIKI Mission Control TUI.
Supports English and Russian languages.
"""

from typing import Dict, Any
from enum import Enum


class Language(Enum):
    """Available languages."""
    ENGLISH = "en"
    RUSSIAN = "ru"


class I18n:
    """Internationalization manager for the application."""
    
    def __init__(self, default_language: Language = Language.ENGLISH):
        """Initialize i18n with default language."""
        self.current_language = default_language
        self.translations = self._load_translations()
    
    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load all translations."""
        return {
            # Headers and Titles
            "app.title": {
                Language.ENGLISH: "QIKI Mission Control",
                Language.RUSSIAN: "QИКИ Центр Управления Полетом"
            },
            "app.subtitle": {
                Language.ENGLISH: "NASA/Military Command Interface",
                Language.RUSSIAN: "Интерфейс Командования NASA/Военный"
            },
            
            # System Status Panel
            "panel.system_status": {
                Language.ENGLISH: "SYSTEM STATUS",
                Language.RUSSIAN: "СОСТОЯНИЕ СИСТЕМ"
            },
            "system.power": {
                Language.ENGLISH: "POWER",
                Language.RUSSIAN: "ПИТАНИЕ"
            },
            "system.hull": {
                Language.ENGLISH: "HULL",
                Language.RUSSIAN: "КОРПУС"
            },
            "system.life_support": {
                Language.ENGLISH: "LIFE SUPPORT",
                Language.RUSSIAN: "ЖИЗНЕОБЕСПЕЧЕНИЕ"
            },
            "system.computing": {
                Language.ENGLISH: "COMPUTING",
                Language.RUSSIAN: "ВЫЧИСЛЕНИЯ"
            },
            "system.integrity": {
                Language.ENGLISH: "INTEGRITY",
                Language.RUSSIAN: "ЦЕЛОСТНОСТЬ"
            },
            "status.nominal": {
                Language.ENGLISH: "NOMINAL",
                Language.RUSSIAN: "НОМИНАЛЬНЫЙ"
            },
            "status.good": {
                Language.ENGLISH: "GOOD",
                Language.RUSSIAN: "ХОРОШО"
            },
            "status.damaged": {
                Language.ENGLISH: "DAMAGED",
                Language.RUSSIAN: "ПОВРЕЖДЕН"
            },
            "status.warning": {
                Language.ENGLISH: "WARNING",
                Language.RUSSIAN: "ПРЕДУПРЕЖДЕНИЕ"
            },
            "status.normal": {
                Language.ENGLISH: "NORMAL",
                Language.RUSSIAN: "НОРМАЛЬНО"
            },
            "status.active": {
                Language.ENGLISH: "ACTIVE",
                Language.RUSSIAN: "АКТИВЕН"
            },
            
            # Navigation Panel
            "panel.navigation": {
                Language.ENGLISH: "NAVIGATION",
                Language.RUSSIAN: "НАВИГАЦИЯ"
            },
            "nav.position": {
                Language.ENGLISH: "POSITION",
                Language.RUSSIAN: "ПОЗИЦИЯ"
            },
            "nav.velocity": {
                Language.ENGLISH: "VELOCITY",
                Language.RUSSIAN: "СКОРОСТЬ"
            },
            "nav.attitude": {
                Language.ENGLISH: "ATTITUDE",
                Language.RUSSIAN: "ОРИЕНТАЦИЯ"
            },
            "nav.autopilot": {
                Language.ENGLISH: "AUTOPILOT",
                Language.RUSSIAN: "АВТОПИЛОТ"
            },
            "nav.enabled": {
                Language.ENGLISH: "ENABLED",
                Language.RUSSIAN: "ВКЛЮЧЕН"
            },
            "nav.disabled": {
                Language.ENGLISH: "DISABLED",
                Language.RUSSIAN: "ОТКЛЮЧЕН"
            },
            
            # Radar Panel
            "panel.radar": {
                Language.ENGLISH: "RADAR CONTACTS",
                Language.RUSSIAN: "РАДАРНЫЕ ЦЕЛИ"
            },
            "radar.track": {
                Language.ENGLISH: "TRACK",
                Language.RUSSIAN: "ЦЕЛЬ"
            },
            "radar.type": {
                Language.ENGLISH: "TYPE",
                Language.RUSSIAN: "ТИП"
            },
            "radar.range": {
                Language.ENGLISH: "RANGE",
                Language.RUSSIAN: "ДАЛЬНОСТЬ"
            },
            "radar.bearing": {
                Language.ENGLISH: "BEARING",
                Language.RUSSIAN: "ПЕЛЕНГ"
            },
            "radar.velocity": {
                Language.ENGLISH: "VELOCITY",
                Language.RUSSIAN: "СКОРОСТЬ"
            },
            "radar.status": {
                Language.ENGLISH: "STATUS",
                Language.RUSSIAN: "СТАТУС"
            },
            "radar.iff": {
                Language.ENGLISH: "IFF",
                Language.RUSSIAN: "СВОЙ-ЧУЖОЙ"
            },
            "radar.tracking": {
                Language.ENGLISH: "TRACKING",
                Language.RUSSIAN: "СЛЕЖЕНИЕ"
            },
            "radar.ship": {
                Language.ENGLISH: "SHIP",
                Language.RUSSIAN: "КОРАБЛЬ"
            },
            "radar.drone": {
                Language.ENGLISH: "DRONE",
                Language.RUSSIAN: "БПЛА"
            },
            "radar.debris": {
                Language.ENGLISH: "DEBRIS",
                Language.RUSSIAN: "ОБЛОМКИ"
            },
            "radar.friend": {
                Language.ENGLISH: "FRIEND",
                Language.RUSSIAN: "ДРУГ"
            },
            "radar.unknown": {
                Language.ENGLISH: "UNKNOWN",
                Language.RUSSIAN: "НЕИЗВЕСТНЫЙ"
            },
            "radar.neutral": {
                Language.ENGLISH: "NEUTRAL",
                Language.RUSSIAN: "НЕЙТРАЛЬНЫЙ"
            },
            
            # Propulsion Panel
            "panel.propulsion": {
                Language.ENGLISH: "PROPULSION",
                Language.RUSSIAN: "ДВИГАТЕЛЬНАЯ УСТАНОВКА"
            },
            "prop.main_drive": {
                Language.ENGLISH: "MAIN DRIVE",
                Language.RUSSIAN: "ОСНОВНОЙ ДВИГАТЕЛЬ"
            },
            "prop.thrust": {
                Language.ENGLISH: "THRUST",
                Language.RUSSIAN: "ТЯГА"
            },
            "prop.fuel": {
                Language.ENGLISH: "FUEL",
                Language.RUSSIAN: "ТОПЛИВО"
            },
            "prop.delta_v": {
                Language.ENGLISH: "DELTA-V",
                Language.RUSSIAN: "ЗАПАС ΔV"
            },
            "prop.available": {
                Language.ENGLISH: "AVAILABLE",
                Language.RUSSIAN: "ДОСТУПНО"
            },
            "prop.rcs": {
                Language.ENGLISH: "RCS",
                Language.RUSSIAN: "РДО"
            },
            "prop.ready": {
                Language.ENGLISH: "READY",
                Language.RUSSIAN: "ГОТОВ"
            },
            "prop.idle": {
                Language.ENGLISH: "IDLE",
                Language.RUSSIAN: "ПРОСТОЙ"
            },
            "prop.mode": {
                Language.ENGLISH: "MODE",
                Language.RUSSIAN: "РЕЖИМ"
            },
            "prop.manual": {
                Language.ENGLISH: "MANUAL",
                Language.RUSSIAN: "РУЧНОЙ"
            },
            "prop.auto": {
                Language.ENGLISH: "AUTO",
                Language.RUSSIAN: "АВТО"
            },
            "prop.last_burn": {
                Language.ENGLISH: "LAST BURN",
                Language.RUSSIAN: "ПОСЛЕДНЯЯ РАБОТА"
            },
            
            # Power Panel
            "panel.power": {
                Language.ENGLISH: "POWER DISTRIBUTION",
                Language.RUSSIAN: "РАСПРЕДЕЛЕНИЕ ЭНЕРГИИ"
            },
            "power.sources": {
                Language.ENGLISH: "SOURCES",
                Language.RUSSIAN: "ИСТОЧНИКИ"
            },
            "power.reactor": {
                Language.ENGLISH: "REACTOR",
                Language.RUSSIAN: "РЕАКТОР"
            },
            "power.battery": {
                Language.ENGLISH: "BATTERY",
                Language.RUSSIAN: "АККУМУЛЯТОР"
            },
            "power.consumers": {
                Language.ENGLISH: "CONSUMERS",
                Language.RUSSIAN: "ПОТРЕБИТЕЛИ"
            },
            "power.main_systems": {
                Language.ENGLISH: "MAIN SYSTEMS",
                Language.RUSSIAN: "ОСНОВНЫЕ СИСТЕМЫ"
            },
            "power.sensors": {
                Language.ENGLISH: "SENSORS",
                Language.RUSSIAN: "СЕНСОРЫ"
            },
            
            # Event Log Panel
            "panel.events": {
                Language.ENGLISH: "SYSTEM EVENTS",
                Language.RUSSIAN: "СИСТЕМНЫЕ СОБЫТИЯ"
            },
            "event.initialization": {
                Language.ENGLISH: "System initialization complete",
                Language.RUSSIAN: "Инициализация системы завершена"
            },
            "event.sensors_online": {
                Language.ENGLISH: "All sensors online",
                Language.RUSSIAN: "Все сенсоры в сети"
            },
            "event.battery_warning": {
                Language.ENGLISH: "Battery discharge rate elevated",
                Language.RUSSIAN: "Повышенная скорость разряда батареи"
            },
            "event.interface_started": {
                Language.ENGLISH: "Mission Control interface started",
                Language.RUSSIAN: "Интерфейс центра управления запущен"
            },
            "event.telemetry_failed": {
                Language.ENGLISH: "Telemetry update failed",
                Language.RUSSIAN: "Ошибка обновления телеметрии"
            },
            "event.command_executed": {
                Language.ENGLISH: "Command executed",
                Language.RUSSIAN: "Команда выполнена"
            },
            
            # Command Panel
            "panel.command": {
                Language.ENGLISH: "COMMAND INPUT",
                Language.RUSSIAN: "ВВОД КОМАНД"
            },
            "cmd.placeholder": {
                Language.ENGLISH: "Enter command...",
                Language.RUSSIAN: "Введите команду..."
            },
            "cmd.last_command": {
                Language.ENGLISH: "LAST COMMAND",
                Language.RUSSIAN: "ПОСЛЕДНЯЯ КОМАНДА"
            },
            "cmd.status": {
                Language.ENGLISH: "STATUS",
                Language.RUSSIAN: "СТАТУС"
            },
            "cmd.hotkeys": {
                Language.ENGLISH: "HOTKEYS",
                Language.RUSSIAN: "ГОРЯЧИЕ КЛАВИШИ"
            },
            
            # Common UI Elements
            "ui.loading": {
                Language.ENGLISH: "Loading...",
                Language.RUSSIAN: "Загрузка..."
            },
            "ui.help": {
                Language.ENGLISH: "Help",
                Language.RUSSIAN: "Помощь"
            },
            "ui.exit": {
                Language.ENGLISH: "Exit",
                Language.RUSSIAN: "Выход"
            },
            "ui.low": {
                Language.ENGLISH: "LOW",
                Language.RUSSIAN: "НИЗКИЙ"
            },
            "ui.high": {
                Language.ENGLISH: "HIGH",
                Language.RUSSIAN: "ВЫСОКИЙ"
            },
            
            # Help Messages
            "help.commands": {
                Language.ENGLISH: "Commands: thrust <0-100>, rcs <direction> <0-100>, stop",
                Language.RUSSIAN: "Команды: thrust <0-100>, rcs <направление> <0-100>, stop"
            },
            "help.hotkeys": {
                Language.ENGLISH: "F1-Help F2-Radar F3-Systems F4-Power ESC-Exit",
                Language.RUSSIAN: "F1-Помощь F2-Радар F3-Системы F4-Питание ESC-Выход"
            },
        }
    
    def get(self, key: str, **kwargs) -> str:
        """
        Get translated string for the current language.
        
        Args:
            key: Translation key
            **kwargs: Format parameters for the string
            
        Returns:
            Translated string or key if not found
        """
        if key in self.translations:
            text = self.translations[key].get(self.current_language, key)
            if kwargs:
                return text.format(**kwargs)
            return text
        return key
    
    def switch_language(self):
        """Switch between available languages."""
        if self.current_language == Language.ENGLISH:
            self.current_language = Language.RUSSIAN
        else:
            self.current_language = Language.ENGLISH
    
    def set_language(self, language: Language):
        """Set specific language."""
        self.current_language = language
    
    def get_current_language(self) -> Language:
        """Get current language."""
        return self.current_language


# Global instance
_i18n_instance: I18n = None


def get_i18n() -> I18n:
    """Get or create global i18n instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    """
    Shortcut for getting translations.
    
    Args:
        key: Translation key
        **kwargs: Format parameters
        
    Returns:
        Translated string
    """
    return get_i18n().get(key, **kwargs)


def switch_language():
    """Switch to next available language."""
    get_i18n().switch_language()


def set_language(language: Language):
    """Set specific language."""
    get_i18n().set_language(language)