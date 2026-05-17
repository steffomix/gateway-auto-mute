"""
Audio-Controller für Gateway Auto-Mute
Überwacht Lautsprecherpegel und steuert Mikrofonempfindlichkeit
"""
import os
import struct
import subprocess
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
        # Persistenter Monitor-Stream via parec
        self._monitor_process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._current_monitor_source: str = ""
        self._current_peak: float = 0.0
        self._last_data_time: float = 0.0   # Zeitpunkt des letzten gültigen Datenpakets
        self._STREAM_TIMEOUT: float = 1.0   # Sekunden ohne Daten = Sicherheitsfall
        self._monitor_channels: int = 1  # Kanalzahl des aktiven parec-Streams
        self._MONITOR_RATE: int = 8000  # Hz, reicht für Pegelüberwachung
        self._level_only_mode: bool = False  # True wenn nur Level-Monitoring aktiv
        self._fade_start_time: float = 0.0  # Zeitpunkt Beginn Einblendung (0 = inaktiv)
        self._last_routing_check: float = 0.0
        self._ROUTING_CHECK_INTERVAL: float = 2.0  # Sekunden zwischen Routing-Prüfungen
        
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
    
    def _get_source_channels(self, source_name: str) -> int:
        """Gibt die Kanalzahl einer PipeWire/PulseAudio-Quelle zurück (Fallback: 2)."""
        pulse = self._get_pulse_connection()
        if not pulse:
            return 2
        try:
            for src in pulse.source_list():
                if src.name == source_name:
                    return max(1, src.channel_count)
        except Exception:
            pass
        return 2

    def _start_monitor_stream(self, monitor_source_name: str) -> bool:
        """Startet einen persistenten parec-Subprocess für den Monitor-Stream.
        PIPEWIRE_PROPS=node.dont-reconnect=true verhindert, dass WirePlumber
        den Stream nach einem Cinnamon-Gerätewechsel auf das neue Standard-Gerät
        umleitet ("Follow Default"-Policy des Session Managers)."""
        self._stop_monitor_stream()
        channels = self._get_source_channels(monitor_source_name)
        if channels == 1:
            channel_map = 'mono'
        elif channels == 2:
            channel_map = 'front-left,front-right'
        else:
            channel_map = ','.join(['aux' + str(i) for i in range(channels)])

        # PIPEWIRE_PROPS verhindert, dass WirePlumber den parec-Stream auf das
        # neue Standard-Gerät umleitet, wenn Cinnamon den Default-Sink wechselt.
        # node.autoconnect=false muss auf beiden Seiten (playback + capture) gesetzt
        # sein, damit WirePlumber den Stream nicht auto-verbindet (Reddit r/linuxaudio).
        env = os.environ.copy()
        env['PIPEWIRE_PROPS'] = '{ node.dont-reconnect = true, node.autoconnect = false }'

        try:
            self._monitor_channels = channels
            self._monitor_process = subprocess.Popen(
                ['parec',
                 f'--device={monitor_source_name}',
                 '--format=float32le',
                 f'--channels={channels}',
                 f'--channel-map={channel_map}',
                 f'--rate={self._MONITOR_RATE}',
                 f'--latency-msec={max(100, ((int(self.config.get("polling_interval", 50)) + 99) // 100) * 100)}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env
            )
            self._current_monitor_source = monitor_source_name
            self._current_peak = 0.0
            self._last_data_time = time.time()
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True
            )
            self._reader_thread.start()
            return True
        except Exception as e:
            self._update_status(f"Fehler beim Starten des Monitor-Streams: {e}")
            self._monitor_process = None
            return False

    def _reader_loop(self) -> None:
        """Liest kontinuierlich Audio-Daten aus parec, aktualisiert self._current_peak
        und ruft level_callback direkt auf – unabhängig vom Monitoring-Loop."""
        channels = self._monitor_channels
        # 50 ms Chunks: rate * 0.05 s * channels * 4 Bytes (float32)
        chunk_bytes = int(self._MONITOR_RATE * 0.05) * channels * 4
        proc = self._monitor_process
        while self.running and proc and proc.poll() is None:
            try:
                data = proc.stdout.read(chunk_bytes)
                if not data:
                    break
                n = len(data) // 4
                if n > 0:
                    samples = struct.unpack(f'{n}f', data[:n * 4])
                    if channels > 1:
                        frames = n // channels
                        peak = 0.0
                        for i in range(frames):
                            fp = max(abs(samples[i * channels + c]) for c in range(channels))
                            if fp > peak:
                                peak = fp
                        self._current_peak = peak
                    else:
                        self._current_peak = max(abs(s) for s in samples)
                    if self.level_callback:
                        self.level_callback(min(100.0, self._current_peak * 100.0))
                    self._last_data_time = time.time()
            except Exception:
                break

    def _stop_monitor_stream(self) -> None:
        """Stoppt den parec-Subprocess und den Reader-Thread."""
        proc = self._monitor_process
        self._monitor_process = None
        self._current_monitor_source = ""
        self._monitor_channels = 1
        self._last_data_time = 0.0
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None
        self._current_peak = 0.0

    def _enforce_routing(self, speaker: pulsectl.PulseSinkInfo,
                         microphone: pulsectl.PulseSourceInfo) -> None:
        """Stellt sicher, dass alle Streams der konfigurierten Anwendung
        (routing_app_filter) auf den richtigen Geräten bleiben.
        Wird aufgerufen wenn WirePlumber Streams nach einem Cinnamon-
        Gerätewechsel auf das neue Standard-Gerät umgeleitet hat.

        Prüft:
          • Sink-Inputs  (Ausgabe → speaker)   via pulse.sink_input_move()
          • Source-Outputs (Mikrofon → microphone) via pulse.source_output_move()
        """
        pulse = self._get_pulse_connection()
        if not pulse:
            return

        app_filter = self.config.get("routing_app_filter", "teamspeak").lower()

        try:
            for si in pulse.sink_input_list():
                app = (si.proplist.get('application.name', '')
                       or si.proplist.get('application.process.binary', '')).lower()
                if app_filter in app and si.sink != speaker.index:
                    try:
                        pulse.sink_input_move(si.index, speaker.index)
                        # WirePlumber-Präferenz setzen: Stream dauerhaft auf diesem Gerät halten
                        node_id = si.proplist.get('object.id') or si.proplist.get('node.id', '')
                        if node_id:
                            subprocess.run(
                                ['pw-metadata', str(node_id), 'target.object', speaker.name],
                                capture_output=True, timeout=3
                            )
                        self._update_status(
                            f"Routing: '{si.proplist.get('application.name', app)}' "
                            f"Ausgabe → '{speaker.description}'"
                        )
                    except Exception as e:
                        self._update_status(f"Routing sink-input Fehler: {e}")
        except Exception as e:
            self._update_status(f"Routing: Fehler beim Prüfen der Ausgabe-Streams: {e}")

        try:
            for so in pulse.source_output_list():
                app = (so.proplist.get('application.name', '')
                       or so.proplist.get('application.process.binary', '')).lower()
                if app_filter in app and so.source != microphone.index:
                    try:
                        pulse.source_output_move(so.index, microphone.index)
                        # WirePlumber-Präferenz setzen: Stream dauerhaft auf diesem Gerät halten
                        node_id = so.proplist.get('object.id') or so.proplist.get('node.id', '')
                        if node_id:
                            subprocess.run(
                                ['pw-metadata', str(node_id), 'target.object', microphone.name],
                                capture_output=True, timeout=3
                            )
                        self._update_status(
                            f"Routing: '{so.proplist.get('application.name', app)}' "
                            f"Mikrofon → '{microphone.description}'"
                        )
                    except Exception as e:
                        self._update_status(f"Routing source-output Fehler: {e}")
        except Exception as e:
            self._update_status(f"Routing: Fehler beim Prüfen der Mikrofon-Streams: {e}")

    def _get_sink_audio_level(self, sink: pulsectl.PulseSinkInfo) -> float:
        """Gibt den zuletzt gemessenen Peak-Pegel des Sinks zurück (0–100 %).
        Startet den persistenten parec-Stream neu, falls sich die Monitor-Source
        geändert hat oder der Prozess nicht mehr läuft.
        Sicherheitsschaltung: Wenn der Stream gestartet werden konnte, aber
        keine Daten geliefert hat (Timeout), wird 100 % zurückgegeben damit
        das Mikrofon auf jeden Fall gedämpft bleibt.
        """
        monitor_source = sink.monitor_source_name
        # Stream (neu-)starten wenn nötig
        if (self._current_monitor_source != monitor_source
                or self._monitor_process is None
                or self._monitor_process.poll() is not None):
            if not self._start_monitor_stream(monitor_source):
                # Stream konnte nicht gestartet werden → Sicherheitsfall: muten
                return 100.0

        # Sicherheitsschaltung: Daten-Timeout prüfen
        if self._last_data_time > 0:
            age = time.time() - self._last_data_time
            if age > self._STREAM_TIMEOUT:
                if self.current_state != "muted":
                    self._update_status(
                        f"Sicherheitsschaltung: keine Daten vom Lautsprecher "
                        f"seit {age:.1f}s – Mikrofon wird gedämpft"
                    )
                return 100.0

        peak_percent = min(100.0, self._current_peak * 100.0)
        return peak_percent
    
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
                hold_time = round(self.config.get("hold_time", 500)) / 1000.0  # ms zu s
                fade_in_time = round(self.config.get("fade_in_time", 1000)) / 1000.0  # ms zu s
                polling_interval = max(10, round(self.config.get("polling_interval", 50))) / 1000.0

                # Routing periodisch prüfen und ggf. erzwingen
                now = time.time()
                if now - self._last_routing_check >= self._ROUTING_CHECK_INTERVAL:
                    self._last_routing_check = now
                    self._enforce_routing(speaker, microphone)

                # Aktuellen Peak-Pegel aus dem persistenten Monitor-Stream lesen
                speaker_volume = self._get_sink_audio_level(speaker)

                current_time = time.time()
                time.sleep(polling_interval)

                # Entscheidungslogik
                if speaker_volume > volume_threshold:
                    # Lautsprecher ist laut - Mikrofon dämpfen und Hold-Zeit neu starten
                    self.last_trigger_time = current_time
                    self._fade_start_time = 0.0
                    self._set_source_volume(microphone, mic_muted_level)
                    if self.current_state != "muted":
                        self.current_state = "muted"
                        self._update_status(f"Mikrofon gedämpft (Lautstärke: {speaker_volume:.1f}%)")
                else:
                    # Lautsprecher ist leise
                    time_since_trigger = current_time - self.last_trigger_time

                    if time_since_trigger < hold_time:
                        # Noch in Hold-Zeit
                        self._fade_start_time = 0.0
                        self._set_source_volume(microphone, mic_muted_level)
                        if self.current_state != "muted":
                            self.current_state = "muted"
                    else:
                        # Hold-Zeit abgelaufen – Pegel nochmals prüfen bevor Mikrofon geöffnet wird
                        check_volume = self._get_sink_audio_level(speaker)
                        if check_volume > volume_threshold:
                            # Pegel immer noch zu hoch: Hold-Zeit verlängern
                            self.last_trigger_time = current_time
                            self._fade_start_time = 0.0
                            self._set_source_volume(microphone, mic_muted_level)
                            self._update_status(
                                f"Hold-Zeit verlängert – Pegel noch {check_volume:.1f}% "
                                f"(Schwelle: {volume_threshold}%)"
                            )
                        else:
                            # Pegel sicher unter Schwelle: Mikrofon einblenden
                            if fade_in_time <= 0:
                                self._set_source_volume(microphone, mic_normal_level)
                                if self.current_state != "monitoring":
                                    self.current_state = "monitoring"
                                    self._update_status("Mikrofon normal - überwache...")
                            else:
                                if self._fade_start_time == 0.0:
                                    self._fade_start_time = current_time
                                    self._update_status(
                                        f"Mikrofon blendet ein ({fade_in_time*1000:.0f} ms)..."
                                    )
                                elapsed = current_time - self._fade_start_time
                                t = min(1.0, elapsed / fade_in_time)
                                vol = mic_muted_level + (mic_normal_level - mic_muted_level) * t
                                self._set_source_volume(microphone, vol)
                                if t >= 1.0:
                                    # Fade abgeschlossen – _fade_start_time bleibt gesetzt,
                                    # damit beim nächsten Loop-Durchlauf nicht neu gestartet wird.
                                    # Zurücksetzen erfolgt erst wenn Lautsprecher wieder auslöst.
                                    if self.current_state != "monitoring":
                                        self.current_state = "monitoring"
                                        self._update_status("Mikrofon normal - überwache...")
                                else:
                                    self.current_state = "fading"
                
            except Exception as e:
                self._update_status(f"Fehler in Überwachungsschleife: {e}")
                time.sleep(1)
        
        # Cleanup beim Beenden
        self._stop_monitor_stream()
        if self.pulse:
            try:
                self.pulse.close()
            except:
                pass
            self.pulse = None
        
        self._update_status("Service gestoppt")
    
    def start_level_monitoring_only(self) -> bool:
        """Startet nur den parec-Monitor-Stream für die Pegelanzeige, ohne die
        vollständige Überwachungsschleife. Wird verwendet, wenn ein externer
        Daemon läuft und die GUI nur den Audiopegel anzeigen soll."""
        if self.running:
            return False
        speaker_name = self.config.get("speaker_device", "")
        if not speaker_name:
            return False
        speaker = self._find_sink_by_name(speaker_name)
        if not speaker:
            return False
        self.running = True
        self._level_only_mode = True
        if not self._start_monitor_stream(speaker.monitor_source_name):
            self.running = False
            self._level_only_mode = False
            return False
        return True

    def stop_level_monitoring(self) -> None:
        """Stoppt den Level-Only-Monitor-Stream."""
        self.running = False
        self._level_only_mode = False
        self._stop_monitor_stream()

    def is_level_monitoring(self) -> bool:
        """Gibt True zurück wenn der Level-Monitor aktiv läuft."""
        return (self.running
                and self._level_only_mode
                and self._monitor_process is not None
                and self._monitor_process.poll() is None)

    def start(self) -> bool:
        """Startet den Überwachungs-Service"""
        if self.running:
            return False
        
        # Zustand zurücksetzen für sauberen Start
        self.current_state = "idle"
        self.last_trigger_time = 0
        
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
