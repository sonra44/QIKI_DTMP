"""
Tests for i18n localization functionality.
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.i18n import I18n, get_i18n


class TestI18n:
    """Test I18n localization functionality."""
    
    def test_i18n_initialization_default(self):
        """Test I18n initializes with default language."""
        i18n = I18n()
        assert i18n.current_language == "en"
        assert len(i18n.translations) > 0
    
    def test_i18n_initialization_custom_language(self):
        """Test I18n initializes with custom language."""
        i18n = I18n(language="ru")
        assert i18n.current_language == "ru"
    
    def test_get_available_languages(self):
        """Test getting available languages."""
        i18n = I18n()
        languages = i18n.get_available_languages()
        
        assert "en" in languages
        assert "ru" in languages
        assert len(languages) >= 2
    
    def test_set_language_valid(self):
        """Test setting valid language."""
        i18n = I18n()
        
        # Set to Russian
        i18n.set_language("ru")
        assert i18n.current_language == "ru"
        
        # Set back to English
        i18n.set_language("en")
        assert i18n.current_language == "en"
    
    def test_set_language_invalid(self):
        """Test setting invalid language."""
        i18n = I18n()
        
        # Should fall back to English
        i18n.set_language("invalid_lang")
        assert i18n.current_language == "en"
    
    def test_translate_existing_key_english(self):
        """Test translating existing key in English."""
        i18n = I18n(language="en")
        
        # Test common translations
        assert i18n.translate("app.title") == "QIKI Operator Console"
        assert i18n.translate("buttons.start_simulation") == "Start Simulation"
        assert i18n.translate("buttons.stop_simulation") == "Stop Simulation"
        assert i18n.translate("status.connected") == "Connected"
        assert i18n.translate("status.disconnected") == "Disconnected"
    
    def test_translate_existing_key_russian(self):
        """Test translating existing key in Russian."""
        i18n = I18n(language="ru")
        
        # Test common translations
        assert i18n.translate("app.title") == "Консоль оператора QIKI"
        assert i18n.translate("buttons.start_simulation") == "Запустить симуляцию"
        assert i18n.translate("buttons.stop_simulation") == "Остановить симуляцию"
        assert i18n.translate("status.connected") == "Подключено"
        assert i18n.translate("status.disconnected") == "Отключено"
    
    def test_translate_nonexistent_key(self):
        """Test translating non-existent key."""
        i18n = I18n()
        
        # Should return the key itself
        assert i18n.translate("nonexistent.key") == "nonexistent.key"
        assert i18n.translate("another.missing.key") == "another.missing.key"
    
    def test_translate_with_parameters(self):
        """Test translating with parameters."""
        i18n = I18n(language="en")
        
        # Test message with parameters
        result = i18n.translate("messages.simulation_status", 
                                simulation_id="sim_123", 
                                status="RUNNING")
        expected = "Simulation sim_123 is RUNNING"
        assert result == expected
    
    def test_translate_with_parameters_russian(self):
        """Test translating with parameters in Russian."""
        i18n = I18n(language="ru")
        
        # Test message with parameters
        result = i18n.translate("messages.simulation_status",
                                simulation_id="sim_123",
                                status="ЗАПУЩЕНА")
        expected = "Симуляция sim_123 в состоянии ЗАПУЩЕНА"
        assert result == expected
    
    def test_translate_nested_keys(self):
        """Test translating nested keys."""
        i18n = I18n(language="en")
        
        # Test various nested keys
        assert "Chat" in i18n.translate("panels.chat")
        assert "Simulation" in i18n.translate("panels.simulation")
        assert "Metrics" in i18n.translate("panels.metrics")
    
    def test_translate_shorthand_method(self):
        """Test shorthand translation method."""
        i18n = I18n()
        
        # Both methods should work the same
        full_result = i18n.translate("app.title")
        short_result = i18n.t("app.title")
        
        assert full_result == short_result
        assert short_result == "QIKI Operator Console"
    
    def test_format_message_simple(self):
        """Test simple message formatting."""
        i18n = I18n()
        
        message = "Hello {name}"
        result = i18n._format_message(message, name="World")
        assert result == "Hello World"
    
    def test_format_message_multiple_params(self):
        """Test message formatting with multiple parameters."""
        i18n = I18n()
        
        message = "User {user} started simulation {sim_id} at {time}"
        result = i18n._format_message(message, 
                                      user="operator", 
                                      sim_id="sim_001",
                                      time="12:30")
        expected = "User operator started simulation sim_001 at 12:30"
        assert result == expected
    
    def test_format_message_no_params(self):
        """Test message formatting without parameters."""
        i18n = I18n()
        
        message = "Simple message without parameters"
        result = i18n._format_message(message)
        assert result == message
    
    def test_format_message_missing_params(self):
        """Test message formatting with missing parameters."""
        i18n = I18n()
        
        message = "Hello {name}, your status is {status}"
        result = i18n._format_message(message, name="User")
        # Should return original message when formatting fails
        assert result == message
    
    def test_nested_dictionary_access(self):
        """Test accessing nested dictionary keys."""
        i18n = I18n()
        
        # Test that nested access works
        translations = i18n.translations[i18n.current_language]
        
        # Should have nested structure
        assert "app" in translations
        assert isinstance(translations["app"], dict)
        assert "title" in translations["app"]
    
    def test_language_switching_preserves_translations(self):
        """Test that switching languages preserves all translations."""
        i18n = I18n()
        
        # Get translation in English
        en_title = i18n.translate("app.title")
        
        # Switch to Russian
        i18n.set_language("ru")
        ru_title = i18n.translate("app.title")
        
        # Switch back to English
        i18n.set_language("en")
        en_title_again = i18n.translate("app.title")
        
        # Should be consistent
        assert en_title == en_title_again
        assert en_title != ru_title  # Should be different languages
    
    def test_error_handling_corrupted_translations(self):
        """Test error handling with corrupted translation data."""
        i18n = I18n()
        
        # Simulate corrupted translations
        i18n.translations["en"]["corrupted"] = None
        
        # Should handle gracefully
        result = i18n.translate("corrupted")
        assert result == "corrupted"  # Falls back to key
    
    def test_case_insensitive_language_codes(self):
        """Test case insensitive language codes."""
        i18n = I18n()
        
        # Should work with different cases
        i18n.set_language("EN")
        assert i18n.current_language == "en"
        
        i18n.set_language("Ru")
        assert i18n.current_language == "ru"
        
        i18n.set_language("RU")
        assert i18n.current_language == "ru"


class TestI18nSingleton:
    """Test I18n singleton functionality."""
    
    def test_get_i18n_singleton(self):
        """Test getting I18n singleton instance."""
        i18n1 = get_i18n()
        i18n2 = get_i18n()
        
        # Should be the same instance
        assert i18n1 is i18n2
        assert isinstance(i18n1, I18n)
    
    def test_singleton_preserves_state(self):
        """Test that singleton preserves state across calls."""
        i18n1 = get_i18n()
        i18n1.set_language("ru")
        
        i18n2 = get_i18n()
        assert i18n2.current_language == "ru"
    
    def test_singleton_initialization_once(self):
        """Test that singleton is only initialized once."""
        # Reset global instance to test initialization
        import core.i18n as i18n_module
        original_instance = i18n_module._i18n_instance
        i18n_module._i18n_instance = None
        
        try:
            with patch.object(i18n_module, 'I18n') as mock_class:
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                
                # First call should initialize
                i18n1 = get_i18n()
                
                # Second call should not initialize again
                i18n2 = get_i18n()
                
                # I18n class should only be called once
                assert mock_class.call_count == 1
                # Both calls should return the same instance
                assert i18n1 is i18n2
        finally:
            # Restore original instance
            i18n_module._i18n_instance = original_instance


class TestI18nTranslations:
    """Test specific translation content."""
    
    @pytest.fixture
    def en_i18n(self):
        """Get English I18n instance."""
        return I18n(language="en")
    
    @pytest.fixture
    def ru_i18n(self):
        """Get Russian I18n instance."""
        return I18n(language="ru")
    
    def test_app_translations(self, en_i18n, ru_i18n):
        """Test app-related translations."""
        # English
        assert "QIKI" in en_i18n.translate("app.title")
        assert "Console" in en_i18n.translate("app.title")
        
        # Russian
        assert "QIKI" in ru_i18n.translate("app.title")
        assert "Консоль" in ru_i18n.translate("app.title")
    
    def test_button_translations(self, en_i18n, ru_i18n):
        """Test button-related translations."""
        buttons = [
            "start_simulation",
            "stop_simulation", 
            "send_message",
            "clear_chat",
            "export_data"
        ]
        
        for button in buttons:
            key = f"buttons.{button}"
            
            en_text = en_i18n.translate(key)
            ru_text = ru_i18n.translate(key)
            
            # Should not be the same (different languages)
            assert en_text != ru_text
            # Should not be the key (should be translated)
            assert en_text != key
            assert ru_text != key
    
    def test_status_translations(self, en_i18n, ru_i18n):
        """Test status-related translations."""
        statuses = [
            "connected",
            "disconnected",
            "connecting",
            "error",
            "running",
            "stopped"
        ]
        
        for status in statuses:
            key = f"status.{status}"
            
            en_text = en_i18n.translate(key)
            ru_text = ru_i18n.translate(key)
            
            # Should be translated
            assert en_text != key
            assert ru_text != key
    
    def test_panel_translations(self, en_i18n, ru_i18n):
        """Test panel-related translations."""
        panels = [
            "simulation",
            "chat", 
            "metrics",
            "logs"
        ]
        
        for panel in panels:
            key = f"panels.{panel}"
            
            en_text = en_i18n.translate(key)
            ru_text = ru_i18n.translate(key)
            
            # Should be translated
            assert en_text != key
            assert ru_text != key


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
