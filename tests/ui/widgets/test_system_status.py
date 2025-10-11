"""
Tests for SystemStatusWidget
"""

import pytest
from rich.panel import Panel
from unittest.mock import MagicMock


class TestSystemStatusWidget:
    """Test SystemStatusWidget functionality"""
    
    def test_widget_initialization(self):
        """Test widget initializes with empty data"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        assert widget.ship_data == {}
        
    def test_render_empty_state(self):
        """Test widget renders loading message when no data"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        panel = widget.render()
        
        assert isinstance(panel, Panel)
        assert "Loading system data..." in str(panel.renderable)
        assert panel.title == "SYSTEM STATUS | СОСТОЯНИЕ СИСТЕМ"
        
    def test_update_data(self):
        """Test widget updates data correctly"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        widget.refresh = MagicMock()  # Mock refresh method
        
        test_data = {
            'power': {'reactor_output_mw': 22.5},
            'hull': {'integrity': 95},
        }
        
        widget.update_data(test_data)
        
        assert widget.ship_data == test_data
        widget.refresh.assert_called_once()
        
    def test_render_with_data(self):
        """Test widget renders correctly with data"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        
        test_data = {
            'power': {'reactor_output_mw': 22.5, 'battery_charge_mwh': 4.8},
            'hull': {'integrity': 95, 'mass_kg': 1000},
            'life_support': {'oxygen_percent': 21.0},
            'computing': {'qiki_temperature_k': 318, 'qiki_core_status': 'ACTIVE'}
        }
        
        widget.update_data(test_data)
        panel = widget.render()
        
        assert isinstance(panel, Panel)
        
        # Check content includes expected elements
        content = str(panel.renderable)
        assert "POWER" in content
        assert "22.5 MW" in content
        assert "HULL" in content
        assert "95%" in content
        assert "LIFE SUP" in content
        assert "O2: 21.0%" in content
        assert "COMPUTE" in content
        assert "318 K" in content
        assert "ACTIVE" in content
        
    def test_progress_bar_creation(self):
        """Test progress bar generation"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        
        # Test various percentages
        assert widget._create_progress_bar(0) == "[░░░░░░░░░░]"
        assert widget._create_progress_bar(50) == "[█████░░░░░]"
        assert widget._create_progress_bar(100) == "[██████████]"
        assert widget._create_progress_bar(75) == "[███████░░░]"
        
    def test_hull_status_logic(self):
        """Test hull status shows GOOD/DAMAGED correctly"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        
        # Test GOOD status
        widget.ship_data = {'hull': {'integrity': 95}}
        panel = widget.render()
        assert "GOOD" in str(panel.renderable)
        
        # Test DAMAGED status
        widget.ship_data = {'hull': {'integrity': 85}}
        panel = widget.render()
        assert "DAMAGED" in str(panel.renderable)
        
    def test_life_support_warning(self):
        """Test life support shows warning for abnormal O2"""
        from src.qiki.ui.widgets.system_status import SystemStatusWidget
        
        widget = SystemStatusWidget()
        
        # Normal O2
        widget.ship_data = {'life_support': {'oxygen_percent': 21.0}}
        panel = widget.render()
        assert "NORMAL" in str(panel.renderable)
        
        # Abnormal O2
        widget.ship_data = {'life_support': {'oxygen_percent': 18.0}}
        panel = widget.render()
        assert "WARNING" in str(panel.renderable)