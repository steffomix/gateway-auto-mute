"""
Audio-Controller für Gateway Auto-Mute
Überwacht Lautsprecherpegel und steuert Mikrofonempfindlichkeit
"""
import time
import threading
import pulsectl
from typing import Optional, Callable
from config import Config


class AudioController:
    """Kontrolliert Audio-Geräte und implementiert die Auto-Mute-Logik"""
    
    def __init__(self, config: Config, status_callback: Optional[Callable] = None,
                 level_callback: Optional[Callable] = None):
        self.config = config
        self.status_callback = status_callback
        self.level_callback = level_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.pulse: Optional[pulsectl.Pulse] = None
        self.speaker_muted = False
        self.mic_muted = False
        self.last_trigger_time = 0
        self.current_state = "idle"  # idle, monitoring, muted
        
    def _update_status(self, message: str) -> None:
        """Sendet Statusmeldung an Callback"""
        print(message)  # Für Debugging
        if self.status_callback:
            self.status_callback(message)
    
    def _get_pulse_connection(self) -> Optional[pulsectl.Pulse]:
        """Erstellt oder aktualisiert PulseAudio-Verbindung"""
        try:
            if self.pulse is None:
                self.pulse = pulsectl.Pulse('gateway-auto-mute')
            return self.pulse
        except Exception as e:
            self._update_status(f"PulseAudio-Verbindungsfehler: {e}")
            self.pulse = None
            return None
    
    def _find_sink_by_name(self, name: str) -> Optional[pulsectl.PulseSinkInfo]:
        """Findet ein Ausgabegerät (Lautsprecher) nach Namen"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return None
        
        try:
            sinks = pulse.sink_list()
            for sink in sinks:
                if name in sink.name or name in sink.description:
                    return sink
        except Exception as e:
            self._update_status(f"Fehler beim Suchen des Lautsprechers: {e}")
        
        return None
    
    def _find_source_by_name(self, name: str) -> Optional[pulsectl.PulseSourceInfo]:
        """Findet ein Eingabegerät (Mikrofon) nach Namen"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return None
        
        try:
            sources = pulse.source_list()
            for source in sources:
                if name in source.name or name in source.description:
                    return source
        except Exception as e:
            self._update_status(f"Fehler beim Suchen des Mikrofons: {e}")
        
        return None
    
    def _get_sink_audio_level(self, sink: pulsectl.PulseSinkInfo, duration: float) -> float:
        """Misst den tatsächlichen Audio-Pegel eines Sinks via PulseAudio Monitor-Source"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return 0.0
        try:
            peak = pulse.get_peak_sample(sink.monitor_source_name, duration)
            peak_percent = min(100.0, peak * 100.0)
            if self.level_callback:
                self.level_callback(peak_percent)
            return peak_percent
        except Exception as e:
            self._update_status(f"Fehler beim Messen des Audio-Pegels: {e}")
            return 0.0
    
    def _set_source_volume(self, source: pulsectl.PulseSourceInfo, volume_percent: float) -> None:
        """Setzt Mikrofon-Empfindlichkeit (0-100%)"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return
        
        try:
            # Konvertiere Prozent zu PulseAudio-Wert (0.0-1.0)
            volume_value = max(0.0, min(1.0, volume_percent / 100.0))
            pulse.volume_set_all_chans(source, volume_value)
        except Exception as e:
            self._update_status(f"Fehler beim Setzen der Mikrofonlautstärke: {e}")
    
    def _is_device_muted(self, device) -> bool:
        """Prüft, ob ein Gerät stumm geschaltet ist"""
        try:
            return bool(device.mute)
        except:
            return False
    
    def _monitoring_loop(self) -> None:
        """Haupt-Überwachungsschleife"""
        self._update_status("Service gestartet")
        
        while self.running:
            try:
                # Hole Geräte
                speaker_name = self.config.get("speaker_device", "")
                mic_name = self.config.get("microphone_device", "")
                
                if not speaker_name or not mic_name:
                    self.current_state = "idle"
                    self._update_status("Geräte nicht konfiguriert")
                    time.sleep(1)
                    continue
                
                speaker = self._find_sink_by_name(speaker_name)
                microphone = self._find_source_by_name(mic_name)
                
                if not speaker or not microphone:
                    self.current_state = "idle"
                    self._update_status("Geräte nicht gefunden - warte...")
                    time.sleep(1)
                    continue
                
                # Prüfe Mute-Status
                speaker_muted = self._is_device_muted(speaker)
                mic_muted = self._is_device_muted(microphone)
                
                if speaker_muted or mic_muted:
                    self.current_state = "idle"
                    # Setze Mikrofon auf Normalpegel wenn im Idle
                    normal_level = self.config.get("mic_normal_level", 80)
                    self._set_source_volume(microphone, normal_level)
                    time.sleep(0.5)
                    continue
                
                # Hole Konfigurationswerte
                volume_threshold = self.config.get("volume_threshold", 10)
                mic_normal_level = self.config.get("mic_normal_level", 80)
                mic_muted_level = self.config.get("mic_muted_level", 10)
                hold_time = self.config.get("hold_time", 500) / 1000.0  # ms zu s
                polling_interval = max(10, self.config.get("polling_interval", 50)) / 1000.0
                
                # Messe tatsächlichen Audio-Pegel über das Intervall
                speaker_volume = self._get_sink_audio_level(speaker, polling_interval)

                current_time = time.time()


                
                # Entscheidungslogik
                if speaker_volume > volume_threshold:
                    # Lautsprecher ist laut - Mikrofon dämpfen
                    self.last_trigger_time = current_time
                    if self.current_state != "muted":
                        self._set_source_volume(microphone, mic_muted_level)
                        self.current_state = "muted"
                        self._update_status(f"Mikrofon gedämpft (Lautstärke: {speaker_volume:.1f}%)")
                else:
                    # Lautsprecher ist leise
                    time_since_trigger = current_time - self.last_trigger_time
                    
                    if time_since_trigger < hold_time:
                        # Noch in Hold-Zeit
                        if self.current_state != "muted":
                            self._set_source_volume(microphone, mic_muted_level)
                            self.current_state = "muted"
                    else:
                        # Hold-Zeit vorbei - Mikrofon normalisieren
                        if self.current_state != "monitoring":
                            self._set_source_volume(microphone, mic_normal_level)
                            self.current_state = "monitoring"
                            self._update_status("Mikrofon normal - überwache...")
                
            except Exception as e:
                self._update_status(f"Fehler in Überwachungsschleife: {e}")
                time.sleep(1)
        
        # Cleanup beim Beenden
        if self.pulse:
            try:
                self.pulse.close()
            except:
                pass
            self.pulse = None
        
        self._update_status("Service gestoppt")
    
    def start(self) -> bool:
        """Startet den Überwachungs-Service"""
        if self.running:
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self) -> None:
        """Stoppt den Überwachungs-Service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
    
    def is_running(self) -> bool:
        """Gibt zurück, ob der Service läuft"""
        return self.running
    
    def get_available_speakers(self) -> list:
        """Gibt Liste verfügbarer Lautsprecher zurück"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return []
        
        try:
            sinks = pulse.sink_list()
            return [{"name": s.name, "description": s.description} for s in sinks]
        except Exception as e:
            self._update_status(f"Fehler beim Abrufen der Lautsprecher: {e}")
            return []
    
    def get_available_microphones(self) -> list:
        """Gibt Liste verfügbarer Mikrofone zurück"""
        pulse = self._get_pulse_connection()
        if not pulse:
            return []
        
        try:
            sources = pulse.source_list()
            # Filtere Monitor-Quellen aus
            return [{"name": s.name, "description": s.description} 
                    for s in sources if not s.name.endswith(".monitor")]
        except Exception as e:
            self._update_status(f"Fehler beim Abrufen der Mikrofone: {e}")
            return []
