"""
Konfigurationsmodul für Gateway Auto-Mute
"""
import json
import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Verwaltung der Konfiguration für das Gateway Auto-Mute System"""
    
    DEFAULT_CONFIG = {
        # Geräte
        "speaker_device": "",  # Name oder Index der Lautsprecher-Soundkarte
        "microphone_device": "",  # Name oder Index der Mikrofon-Soundkarte
        
        # Schwellwerte und Pegel (in Prozent, 0-100)
        "volume_threshold_min": 0,
        "volume_threshold_max": 100,
        "volume_threshold": 10,  # Ab diesem Pegel wird das Mikrofon gedämpft
        
        "mic_normal_level_min": 0,
        "mic_normal_level_max": 100,
        "mic_normal_level": 80,  # Normaler Mikrofonpegel
        
        "mic_muted_level_min": 0,
        "mic_muted_level_max": 100,
        "mic_muted_level": 10,  # Gedämpfter Mikrofonpegel
        
        # Zeiteinstellungen (in Millisekunden)
        "hold_time_min": 0,
        "hold_time_max": 5000,
        "hold_time": 500,  # Zeit, die das Mikrofon gedämpft bleibt
        
        "polling_interval_min": 10,
        "polling_interval_max": 1000,
        "polling_interval": 50,  # Intervall für Lautstärkemessung
    }
    
    def __init__(self, config_file: str = None):
        if config_file is None:
            config_dir = Path.home() / ".config" / "gateway-auto-mute"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"
        
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self) -> None:
        """Lädt die Konfiguration aus der Datei"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
                print("Verwende Standard-Konfiguration")
    
    def save(self) -> None:
        """Speichert die Konfiguration in die Datei"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def get(self, key: str, default=None) -> Any:
        """Gibt einen Konfigurationswert zurück"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Setzt einen Konfigurationswert"""
        self.config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """Gibt die gesamte Konfiguration zurück"""
        return self.config.copy()
    
    def reset_to_defaults(self) -> None:
        """Setzt die Konfiguration auf Standardwerte zurück"""
        self.config = self.DEFAULT_CONFIG.copy()
