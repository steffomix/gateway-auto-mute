#!/usr/bin/env python3
"""
Service-Manager für Gateway Auto-Mute
Ermöglicht das Starten, Stoppen und Überwachen des Hintergrund-Services
"""
import sys
import os
import time
import signal
import subprocess
import json
from pathlib import Path
from config import Config
from audio_controller import AudioController


class ServiceManager:
    """Verwaltet den Gateway Auto-Mute Service"""
    
    def __init__(self):
        self.config = Config()
        self.pid_file = Path.home() / ".config" / "gateway-auto-mute" / "service.pid"
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _write_pid(self, pid: int):
        """Schreibt PID in Datei"""
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))
    
    def _read_pid(self) -> int:
        """Liest PID aus Datei"""
        if not self.pid_file.exists():
            return None
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except:
            return None
    
    def _delete_pid(self):
        """Löscht PID-Datei"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def _is_process_running(self, pid: int) -> bool:
        """Prüft, ob ein Prozess mit der gegebenen PID läuft"""
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def start(self) -> bool:
        """Startet den Service als unabh\u00e4ngigen Hintergrundprozess"""
        existing_pid = self._read_pid()
        if existing_pid and self._is_process_running(existing_pid):
            print(f"Service l\u00e4uft bereits (PID: {existing_pid})")
            return False

        self._delete_pid()

        # Starte einen komplett neuen Python-Prozess (kein fork),
        # damit kein PulseAudio-Zustand aus dem Elternprozess vererbt wird.
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), '_daemon'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

        # Warte bis der Daemon seine PID geschrieben hat
        for _ in range(50):  # bis zu 5 Sekunden
            time.sleep(0.1)
            daemon_pid = self._read_pid()
            if daemon_pid:
                print(f"Service gestartet (PID: {daemon_pid})")
                return True
        print("Service konnte nicht gestartet werden (Timeout)")
        return False

    def _run_as_daemon(self):
        """Wird als eigenst\u00e4ndiger Daemon-Prozess ausgef\u00fchrt"""
        self._write_pid(os.getpid())

        log_dir = Path.home() / ".config" / "gateway-auto-mute"
        log_file = log_dir / "service.log"

        # Log-Datei \u00f6ffnen und stdout/stderr umleiten
        log_fh = open(log_file, 'a', buffering=1)
        sys.stdout = log_fh
        sys.stderr = log_fh

        def status_callback(msg):
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {msg}", flush=True)

        controller = AudioController(self.config, status_callback)

        def signal_handler(signum, frame):
            print(f"Signal {signum} empfangen, beende Service...", flush=True)
            controller.stop()
            self._delete_pid()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        controller.start()

        while controller.is_running():
            time.sleep(1)

        self._delete_pid()
        sys.exit(0)
    
    def stop(self) -> bool:
        """Stoppt den Service"""
        pid = self._read_pid()
        if not pid:
            print("Service läuft nicht (keine PID-Datei)")
            return False
        
        if not self._is_process_running(pid):
            print(f"Prozess {pid} läuft nicht mehr")
            self._delete_pid()
            return False
        
        try:
            os.kill(pid, signal.SIGTERM)
            # Warte kurz auf Beendigung
            for _ in range(10):
                if not self._is_process_running(pid):
                    self._delete_pid()
                    print(f"Service gestoppt (PID: {pid})")
                    return True
                time.sleep(0.5)
            
            # Force kill wenn SIGTERM nicht funktioniert
            os.kill(pid, signal.SIGKILL)
            self._delete_pid()
            print(f"Service forciert beendet (PID: {pid})")
            return True
            
        except OSError as e:
            print(f"Fehler beim Stoppen des Service: {e}")
            return False
    
    def status(self):
        """Zeigt den Status des Service"""
        pid = self._read_pid()
        
        print("=== Gateway Auto-Mute Service Status ===\n")
        
        if not pid:
            print("Status: Gestoppt (keine PID-Datei)")
        elif self._is_process_running(pid):
            print(f"Status: Läuft (PID: {pid})")
        else:
            print(f"Status: Gestoppt (PID {pid} läuft nicht mehr)")
            self._delete_pid()
        
        print("\n=== Konfiguration ===\n")
        self.show_config()
        
        # Log-Datei anzeigen
        log_file = Path.home() / ".config" / "gateway-auto-mute" / "service.log"
        if log_file.exists():
            print("\n=== Letzte Log-Einträge ===\n")
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Zeige letzte 10 Zeilen
                        print(line.rstrip())
            except Exception as e:
                print(f"Fehler beim Lesen der Log-Datei: {e}")
    
    def show_config(self):
        """Zeigt die aktuelle Konfiguration"""
        config = self.config.get_all()
        
        print(f"Lautsprecher: {config.get('speaker_device', 'Nicht konfiguriert')}")
        print(f"Mikrofon: {config.get('microphone_device', 'Nicht konfiguriert')}")
        print(f"\nLautstärke-Schwellwert: {config.get('volume_threshold', 0):.1f}% "
              f"(Min: {config.get('volume_threshold_min', 0):.0f}%, "
              f"Max: {config.get('volume_threshold_max', 100):.0f}%)")
        print(f"Normaler Mikrofon-Pegel: {config.get('mic_normal_level', 0):.1f}% "
              f"(Min: {config.get('mic_normal_level_min', 0):.0f}%, "
              f"Max: {config.get('mic_normal_level_max', 100):.0f}%)")
        print(f"Gedämpfter Mikrofon-Pegel: {config.get('mic_muted_level', 0):.1f}% "
              f"(Min: {config.get('mic_muted_level_min', 0):.0f}%, "
              f"Max: {config.get('mic_muted_level_max', 100):.0f}%)")
        print(f"\nHaltezeit: {config.get('hold_time', 0):.0f}ms "
              f"(Min: {config.get('hold_time_min', 0):.0f}ms, "
              f"Max: {config.get('hold_time_max', 5000):.0f}ms)")
        print(f"Messintervall: {config.get('polling_interval', 0):.0f}ms "
              f"(Min: {config.get('polling_interval_min', 10):.0f}ms, "
              f"Max: {config.get('polling_interval_max', 1000):.0f}ms)")
    
    def restart(self):
        """Startet den Service neu"""
        print("Stoppe Service...")
        self.stop()
        time.sleep(1)
        print("Starte Service...")
        return self.start()


def main():
    if len(sys.argv) < 2:
        print("Verwendung: python3 service_manager.py [start|stop|restart|status|config]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    manager = ServiceManager()
    
    if command == "start":
        success = manager.start()
        sys.exit(0 if success else 1)

    elif command == "_daemon":
        manager._run_as_daemon()

    elif command == "stop":
        success = manager.stop()
        sys.exit(0 if success else 1)
    
    elif command == "restart":
        success = manager.restart()
        sys.exit(0 if success else 1)
    
    elif command == "status":
        manager.status()
        sys.exit(0)
    
    elif command == "config":
        print("=== Gateway Auto-Mute Konfiguration ===\n")
        manager.show_config()
        sys.exit(0)
    
    else:
        print(f"Unbekannter Befehl: {command}")
        print("Verfügbare Befehle: start, stop, restart, status, config")
        sys.exit(1)


if __name__ == "__main__":
    main()
