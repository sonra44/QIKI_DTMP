"""
Data export utilities for Operator Console.

Provides export functionality for telemetry data to CSV and JSON formats.
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import deque
import logging


logger = logging.getLogger(__name__)


class DataExporter:
    """Export telemetry and event data to various formats."""
    
    def __init__(self, export_dir: str = "/app/exports"):
        """
        Initialize data exporter.
        
        Args:
            export_dir: Directory to save exported files
        """
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
    def export_to_json(self, data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Export data to JSON file.
        
        Args:
            data: Data to export
            filename: Optional filename (auto-generated if not provided)
            
        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"qiki_export_{timestamp}.json"
            
        filepath = self.export_dir / filename
        
        try:
            # Convert deque objects to lists for JSON serialization
            serializable_data = self._make_serializable(data)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, default=str)
                
            logger.info(f"✅ Exported data to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Failed to export JSON: {e}")
            raise
            
    def export_to_csv(self, data: List[Dict[str, Any]], filename: Optional[str] = None,
                      headers: Optional[List[str]] = None) -> str:
        """
        Export tabular data to CSV file.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename
            headers: Optional list of headers (auto-detected if not provided)
            
        Returns:
            Path to exported file
        """
        if not data:
            raise ValueError("No data to export")
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"qiki_telemetry_{timestamp}.csv"
            
        filepath = self.export_dir / filename
        
        try:
            # Auto-detect headers if not provided
            if headers is None:
                headers = list(data[0].keys())
                
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
                
            logger.info(f"✅ Exported {len(data)} rows to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Failed to export CSV: {e}")
            raise
            
    def export_telemetry(self, telemetry_buffer: Dict[str, Any], 
                        format: str = "json") -> str:
        """
        Export telemetry data.
        
        Args:
            telemetry_buffer: Telemetry data to export
            format: Export format ('json' or 'csv')
            
        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "json":
            json_payload = {
                "export_timestamp": datetime.now().isoformat(),
                "telemetry": telemetry_buffer
            }
            return self.export_to_json(json_payload, f"telemetry_{timestamp}.json")
            
        elif format == "csv":
            # Convert telemetry to list format for CSV
            rows: List[Dict[str, str]] = []
            for key, value in telemetry_buffer.items():
                rows.append({
                    "timestamp": datetime.now().isoformat(),
                    "metric": key,
                    "value": str(value)
                })
            return self.export_to_csv(rows, f"telemetry_{timestamp}.csv")
            
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    def export_radar_frames(self, frames_buffer: deque, format: str = "json") -> str:
        """
        Export radar frames data.
        
        Args:
            frames_buffer: Deque of radar frames
            format: Export format
            
        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        frames_list = list(frames_buffer)
        
        if format == "json":
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "frame_count": len(frames_list),
                "frames": frames_list
            }
            return self.export_to_json(data, f"radar_frames_{timestamp}.json")
            
        elif format == "csv":
            # Flatten radar frames for CSV
            csv_data = []
            for frame in frames_list:
                csv_data.append({
                    "timestamp": frame.get("timestamp", ""),
                    "frame_id": frame.get("frame_id", ""),
                    "sensor_id": frame.get("sensor_id", ""),
                    "detections": frame.get("detections", 0)
                })
            return self.export_to_csv(csv_data, f"radar_frames_{timestamp}.csv")
            
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    def export_events(self, events_buffer: deque, format: str = "json") -> str:
        """
        Export system events.
        
        Args:
            events_buffer: Deque of events
            format: Export format
            
        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        events_list = list(events_buffer)
        
        if format == "json":
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "event_count": len(events_list),
                "events": events_list
            }
            return self.export_to_json(data, f"events_{timestamp}.json")
            
        elif format == "csv":
            # Format events for CSV
            csv_data = []
            for event in events_list:
                csv_data.append({
                    "timestamp": event.get("timestamp", ""),
                    "type": event.get("type", ""),
                    "severity": event.get("severity", ""),
                    "message": event.get("message", "")
                })
            return self.export_to_csv(csv_data, f"events_{timestamp}.csv")
            
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    def export_full_session(self, session_data: Dict[str, Any]) -> str:
        """
        Export complete session data.
        
        Args:
            session_data: Complete session data including all buffers
            
        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "session_id": session_data.get("session_id", "unknown"),
            "uptime_seconds": session_data.get("uptime_seconds", 0),
            "statistics": session_data.get("stats", {}),
            "telemetry": session_data.get("telemetry_buffer", {}),
            "radar_frames": list(session_data.get("radar_frames_buffer", [])),
            "events": list(session_data.get("events_buffer", [])),
            "commands": list(session_data.get("command_history", [])),
            "chat_history": list(session_data.get("chat_history", []))
        }
        
        return self.export_to_json(export_data, f"session_{timestamp}.json")
        
    def _make_serializable(self, obj: Any) -> Any:
        """
        Convert objects to JSON-serializable format.
        
        Args:
            obj: Object to convert
            
        Returns:
            Serializable version of the object
        """
        if isinstance(obj, deque):
            return list(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj
            
    def create_report(self, session_data: Dict[str, Any]) -> str:
        """
        Create a human-readable report from session data.
        
        Args:
            session_data: Session data to report on
            
        Returns:
            Report as string
        """
        report = []
        report.append("=" * 60)
        report.append("QIKI OPERATOR CONSOLE - SESSION REPORT")
        report.append("=" * 60)
        
        # Session info
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Session ID: {session_data.get('session_id', 'N/A')}")
        report.append(f"Uptime: {session_data.get('uptime_seconds', 0)} seconds")
        
        # Statistics
        stats = session_data.get("stats", {})
        report.append("\nSTATISTICS:")
        report.append(f"  Frames Received: {stats.get('frames_received', 0)}")
        report.append(f"  Events Received: {stats.get('events_received', 0)}")
        report.append(f"  Commands Sent: {stats.get('commands_sent', 0)}")
        
        # Current telemetry
        telemetry = session_data.get("telemetry_buffer", {})
        if telemetry:
            report.append("\nLATEST TELEMETRY:")
            for key, value in telemetry.items():
                report.append(f"  {key}: {value}")
                
        # Recent events
        events = list(session_data.get("events_buffer", []))[-5:]
        if events:
            report.append("\nRECENT EVENTS:")
            for event in events:
                report.append(f"  [{event.get('timestamp', 'N/A')}] "
                            f"{event.get('type', 'UNKNOWN')}: "
                            f"{event.get('message', '')}")
                            
        # Command history
        commands = list(session_data.get("command_history", []))[-5:]
        if commands:
            report.append("\nRECENT COMMANDS:")
            for cmd in commands:
                report.append(f"  [{cmd.get('timestamp', 'N/A')}] "
                            f"{cmd.get('command', '')}")
                            
        report.append("\n" + "=" * 60)
        report.append("END OF REPORT")
        report.append("=" * 60)
        
        return "\n".join(report)


class DataLogger:
    """Log data continuously to files."""
    
    def __init__(self, log_dir: str = "/app/logs", max_size_mb: int = 100):
        """
        Initialize data logger.
        
        Args:
            log_dir: Directory for log files
            max_size_mb: Maximum log file size in MB
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        
        # Create log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.telemetry_log = self.log_dir / f"telemetry_{timestamp}.jsonl"
        self.events_log = self.log_dir / f"events_{timestamp}.jsonl"
        self.radar_log = self.log_dir / f"radar_{timestamp}.jsonl"
        
    def log_telemetry(self, data: Dict[str, Any]):
        """Log telemetry data."""
        self._append_jsonl(self.telemetry_log, data)
        
    def log_event(self, event: Dict[str, Any]):
        """Log system event."""
        self._append_jsonl(self.events_log, event)
        
    def log_radar_frame(self, frame: Dict[str, Any]):
        """Log radar frame."""
        self._append_jsonl(self.radar_log, frame)
        
    def _append_jsonl(self, filepath: Path, data: Dict[str, Any]):
        """
        Append data to JSON Lines file.
        
        Args:
            filepath: Path to log file
            data: Data to append
        """
        try:
            # Check file size and rotate if needed
            if filepath.exists() and filepath.stat().st_size > self.max_size:
                self._rotate_log(filepath)
                
            # Append data
            with open(filepath, 'a', encoding='utf-8') as f:
                json.dump(data, f, default=str)
                f.write('\n')
                
        except Exception as e:
            logger.error(f"Failed to log data: {e}")
            
    def _rotate_log(self, filepath: Path):
        """Rotate log file when it gets too large."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = filepath.stem + f"_{timestamp}" + filepath.suffix
        new_path = filepath.parent / new_name
        filepath.rename(new_path)
        logger.info(f"Rotated log file: {filepath} -> {new_path}")


# Example usage
if __name__ == "__main__":
    # Test data export
    exporter = DataExporter("/tmp/exports")
    
    # Sample telemetry data
    telemetry = {
        "position_x": 10.5,
        "position_y": 20.3,
        "velocity": 5.2,
        "battery": 85
    }
    
    # Export telemetry
    json_file = exporter.export_telemetry(telemetry, format="json")
    print(f"Exported telemetry to JSON: {json_file}")
    
    csv_file = exporter.export_telemetry(telemetry, format="csv")
    print(f"Exported telemetry to CSV: {csv_file}")
    
    # Create session report
    session_data = {
        "session_id": "test_session",
        "uptime_seconds": 300,
        "stats": {
            "frames_received": 1234,
            "events_received": 56,
            "commands_sent": 12
        },
        "telemetry_buffer": telemetry
    }
    
    report = exporter.create_report(session_data)
    print("\nSession Report:")
    print(report)
