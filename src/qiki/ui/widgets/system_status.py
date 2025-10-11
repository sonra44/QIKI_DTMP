"""
System Status Widget for QIKI Mission Control TUI
Displays ship systems health and status
"""

from typing import Dict, Any
from textual.widgets import Static
from rich.panel import Panel


class SystemStatusWidget(Static):
    """System status panel widget"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ship_data: Dict[str, Any] = {}
        
    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with new ship data"""
        self.ship_data = data
        self.refresh()
        
    def render(self) -> Panel:
        """Render system status panel"""
        if not self.ship_data:
            return Panel("Loading system data...", title="SYSTEM STATUS | СОСТОЯНИЕ СИСТЕМ")
            
        # Create status content
        content = []
        
        # Power status
        power = self.ship_data.get('power', {})
        power_pct = int((power.get('reactor_output_mw', 0) / 25.0) * 100)
        power_bar = self._create_progress_bar(power_pct)
        content.append(f"POWER     │ ПИТАНИЕ      {power_bar}   {power_pct}%")
        content.append(f"          │              {power.get('reactor_output_mw', 0):.1f} MW    NOMINAL")
        content.append("")
        
        # Hull status
        hull = self.ship_data.get('hull', {})
        hull_pct = int(hull.get('integrity', 0))
        hull_bar = self._create_progress_bar(hull_pct)
        content.append(f"HULL      │ КОРПУС       {hull_bar}   {hull_pct}%")
        content.append(f"          │              INTEGRITY  {'GOOD' if hull_pct > 90 else 'DAMAGED'}")
        content.append("")
        
        # Life support
        life = self.ship_data.get('life_support', {})
        o2_pct = life.get('oxygen_percent', 21.0)
        life_status = "NORMAL" if 20.0 <= o2_pct <= 22.0 else "WARNING"
        life_bar = self._create_progress_bar(95)  # Usually nominal
        content.append(f"LIFE SUP  │ ЖО           {life_bar}  100%")
        content.append(f"          │              O2: {o2_pct:.1f}%   {life_status}")
        content.append("")
        
        # Computing
        computing = self.ship_data.get('computing', {})
        comp_temp = computing.get('qiki_temperature_k', 318)
        comp_status = computing.get('qiki_core_status', 'ACTIVE')
        comp_bar = self._create_progress_bar(100 if comp_status == 'ACTIVE' else 0)
        content.append(f"COMPUTE   │ ВЫЧИСЛЕНИЯ   {comp_bar}  100%")
        content.append(f"          │              {comp_temp:.0f} K      {comp_status}")
        
        panel_content = "\n".join(content)
        return Panel(
            panel_content, 
            title="SYSTEM STATUS | СОСТОЯНИЕ СИСТЕМ",
            border_style="bright_blue"
        )
    
    def _create_progress_bar(self, percentage: int) -> str:
        """Create ASCII progress bar"""
        filled = int(percentage / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}]"