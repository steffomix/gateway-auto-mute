#!/usr/bin/env python3
"""
Grafische Benutzeroberfläche für Gateway Auto-Mute
"""
import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
from pathlib import Path
import sys
from config import Config
from audio_controller import AudioController


class ConfigSlider(ttk.Frame):
    """Benutzerdefinierter Schieberegler mit Min/Max-Textfeldern"""
    
    def __init__(self, parent, label, config_key, config: Config, 
                 min_key, max_key, unit="", **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.config_key = config_key
        self.min_key = min_key
        self.max_key = max_key
        
        # Label
        ttk.Label(self, text=label).grid(row=0, column=0, columnspan=5, sticky=tk.W, pady=(5, 0))
        
        # Min-Wert Eingabe
        ttk.Label(self, text="Min:").grid(row=1, column=0, padx=(0, 5))
        self.min_var = tk.StringVar(value=str(config.get(min_key, 0)))
        min_entry = ttk.Entry(self, textvariable=self.min_var, width=8)
        min_entry.grid(row=1, column=1, padx=(0, 10))
        min_entry.bind('<FocusOut>', self._on_min_changed)
        min_entry.bind('<Return>', self._on_min_changed)
        
        # Slider
        self.value_var = tk.DoubleVar(value=config.get(config_key, 0))
        self.slider = ttk.Scale(
            self, 
            from_=config.get(min_key, 0), 
            to=config.get(max_key, 100),
            orient=tk.HORIZONTAL,
            variable=self.value_var,
            command=self._on_slider_changed
        )
        self.slider.grid(row=1, column=2, sticky=tk.EW, padx=5)
        self.columnconfigure(2, weight=1)
        
        # Max-Wert Eingabe
        ttk.Label(self, text="Max:").grid(row=1, column=3, padx=(10, 5))
        self.max_var = tk.StringVar(value=str(config.get(max_key, 100)))
        max_entry = ttk.Entry(self, textvariable=self.max_var, width=8)
        max_entry.grid(row=1, column=4)
        max_entry.bind('<FocusOut>', self._on_max_changed)
        max_entry.bind('<Return>', self._on_max_changed)
        
        # Aktueller Wert
        self.current_label = ttk.Label(self, text=f"{self.value_var.get():.1f} {unit}")
        self.current_label.grid(row=2, column=0, columnspan=5, sticky=tk.W)
        self.unit = unit
    
    def _on_slider_changed(self, value):
        """Callback wenn Slider bewegt wird"""
        self.current_label.config(text=f"{float(value):.1f} {self.unit}")
        self.config.set(self.config_key, float(value))
    
    def _on_min_changed(self, event=None):
        """Callback wenn Min-Wert geändert wird"""
        try:
            min_val = float(self.min_var.get())
            max_val = float(self.max_var.get())
            if min_val < max_val:
                self.config.set(self.min_key, min_val)
                self.slider.config(from_=min_val)
                # Stelle sicher, dass aktueller Wert im gültigen Bereich ist
                current = self.value_var.get()
                if current < min_val:
                    self.value_var.set(min_val)
                    self.config.set(self.config_key, min_val)
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Wert für Minimum")
            self.min_var.set(str(self.config.get(self.min_key, 0)))
    
    def _on_max_changed(self, event=None):
        """Callback wenn Max-Wert geändert wird"""
        try:
            min_val = float(self.min_var.get())
            max_val = float(self.max_var.get())
            if max_val > min_val:
                self.config.set(self.max_key, max_val)
                self.slider.config(to=max_val)
                # Stelle sicher, dass aktueller Wert im gültigen Bereich ist
                current = self.value_var.get()
                if current > max_val:
                    self.value_var.set(max_val)
                    self.config.set(self.config_key, max_val)
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Wert für Maximum")
            self.max_var.set(str(self.config.get(self.max_key, 100)))
    
    def get_value(self):
        """Gibt den aktuellen Wert zurück"""
        return self.value_var.get()


class AutoMuteGUI:
    """Hauptfenster der Anwendung"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gateway Auto-Mute Konfiguration")
        self.root.geometry("700x800")
        
        self.config = Config()
        self.audio_controller = AudioController(self.config, self._status_callback)
        
        self._create_widgets()
        self._load_devices()
        
    def _status_callback(self, message: str):
        """Callback für Statusmeldungen"""
        self.root.after(0, lambda: self._update_status(message))
    
    def _update_status(self, message: str):
        """Aktualisiert die Statusanzeige"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def _create_widgets(self):
        """Erstellt alle GUI-Elemente"""
        # Hauptcontainer mit Scrollbar
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        row = 0
        
        # === Geräteauswahl ===
        device_frame = ttk.LabelFrame(main_frame, text="Geräteauswahl", padding="10")
        device_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        # Lautsprecher
        ttk.Label(device_frame, text="Lautsprecher (Output):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.speaker_var = tk.StringVar(value=self.config.get("speaker_device", ""))
        self.speaker_combo = ttk.Combobox(device_frame, textvariable=self.speaker_var, width=50)
        self.speaker_combo.grid(row=0, column=1, padx=(10, 0), pady=5)
        self.speaker_combo.bind('<<ComboboxSelected>>', self._on_speaker_selected)
        
        # Mikrofon
        ttk.Label(device_frame, text="Mikrofon (Input):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mic_var = tk.StringVar(value=self.config.get("microphone_device", ""))
        self.mic_combo = ttk.Combobox(device_frame, textvariable=self.mic_var, width=50)
        self.mic_combo.grid(row=1, column=1, padx=(10, 0), pady=5)
        self.mic_combo.bind('<<ComboboxSelected>>', self._on_mic_selected)
        
        # Refresh-Button
        ttk.Button(device_frame, text="Geräte aktualisieren", 
                   command=self._load_devices).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # === Schwellwerte und Pegel ===
        levels_frame = ttk.LabelFrame(main_frame, text="Pegel und Schwellwerte", padding="10")
        levels_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        self.volume_threshold_slider = ConfigSlider(
            levels_frame, 
            "Lautstärke-Schwellwert (ab diesem Pegel wird Mikrofon gedämpft)",
            "volume_threshold", self.config, 
            "volume_threshold_min", "volume_threshold_max",
            unit="%"
        )
        self.volume_threshold_slider.pack(fill=tk.X, pady=5)
        
        self.mic_normal_slider = ConfigSlider(
            levels_frame,
            "Normaler Mikrofon-Pegel",
            "mic_normal_level", self.config,
            "mic_normal_level_min", "mic_normal_level_max",
            unit="%"
        )
        self.mic_normal_slider.pack(fill=tk.X, pady=5)
        
        self.mic_muted_slider = ConfigSlider(
            levels_frame,
            "Gedämpfter Mikrofon-Pegel",
            "mic_muted_level", self.config,
            "mic_muted_level_min", "mic_muted_level_max",
            unit="%"
        )
        self.mic_muted_slider.pack(fill=tk.X, pady=5)
        
        # === Zeiteinstellungen ===
        time_frame = ttk.LabelFrame(main_frame, text="Zeiteinstellungen", padding="10")
        time_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        self.hold_time_slider = ConfigSlider(
            time_frame,
            "Haltezeit (Mikrofon bleibt gedämpft)",
            "hold_time", self.config,
            "hold_time_min", "hold_time_max",
            unit="ms"
        )
        self.hold_time_slider.pack(fill=tk.X, pady=5)
        
        self.polling_slider = ConfigSlider(
            time_frame,
            "Messintervall (min. 10ms)",
            "polling_interval", self.config,
            "polling_interval_min", "polling_interval_max",
            unit="ms"
        )
        self.polling_slider.pack(fill=tk.X, pady=5)
        
        # === Service-Steuerung ===
        service_frame = ttk.LabelFrame(main_frame, text="Service-Steuerung", padding="10")
        service_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        button_frame = ttk.Frame(service_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="Service starten", command=self._start_service)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Service stoppen", 
                                      command=self._stop_service, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Konfiguration speichern", 
                   command=self._save_config).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Zurücksetzen", 
                   command=self._reset_config).pack(side=tk.LEFT, padx=5)
        
        # === Kommandos ===
        cmd_frame = ttk.LabelFrame(main_frame, text="Kommandos für Terminal", padding="10")
        cmd_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        script_path = Path(__file__).parent / "service_manager.py"
        
        commands = [
            ("Service starten:", f"python3 {script_path} start"),
            ("Service stoppen:", f"python3 {script_path} stop"),
            ("Service-Status:", f"python3 {script_path} status"),
            ("Konfiguration anzeigen:", f"python3 {script_path} config"),
        ]
        
        for i, (label, cmd) in enumerate(commands):
            ttk.Label(cmd_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            cmd_entry = ttk.Entry(cmd_frame, width=60)
            cmd_entry.insert(0, cmd)
            cmd_entry.config(state='readonly')
            cmd_entry.grid(row=i, column=1, padx=(10, 5), pady=2)
            
            ttk.Button(cmd_frame, text="Kopieren", 
                      command=lambda c=cmd: self._copy_to_clipboard(c)).grid(row=i, column=2, pady=2)
        
        # === Status ===
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(row, weight=1)
        row += 1
        
        self.status_text = tk.Text(status_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=scrollbar.set)
        
        main_frame.columnconfigure(0, weight=1)
    
    def _copy_to_clipboard(self, text: str):
        """Kopiert Text in die Zwischenablage"""
        try:
            pyperclip.copy(text)
            self._update_status(f"In Zwischenablage kopiert: {text}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte nicht in Zwischenablage kopieren: {e}")
    
    def _load_devices(self):
        """Lädt verfügbare Audio-Geräte"""
        self._update_status("Lade verfügbare Geräte...")
        
        speakers = self.audio_controller.get_available_speakers()
        microphones = self.audio_controller.get_available_microphones()
        
        speaker_list = [f"{s['description']} ({s['name']})" for s in speakers]
        mic_list = [f"{m['description']} ({m['name']})" for m in microphones]
        
        self.speaker_combo['values'] = speaker_list
        self.mic_combo['values'] = mic_list
        
        # Speichere Mapping von Anzeigename zu internem Namen
        self.speaker_map = {f"{s['description']} ({s['name']})": s['name'] for s in speakers}
        self.mic_map = {f"{m['description']} ({m['name']})": m['name'] for m in microphones}
        
        self._update_status(f"Gefunden: {len(speakers)} Lautsprecher, {len(microphones)} Mikrofone")
    
    def _on_speaker_selected(self, event=None):
        """Callback wenn Lautsprecher ausgewählt wird"""
        selected = self.speaker_var.get()
        if selected in self.speaker_map:
            device_name = self.speaker_map[selected]
            self.config.set("speaker_device", device_name)
            self._update_status(f"Lautsprecher gewählt: {selected}")
    
    def _on_mic_selected(self, event=None):
        """Callback wenn Mikrofon ausgewählt wird"""
        selected = self.mic_var.get()
        if selected in self.mic_map:
            device_name = self.mic_map[selected]
            self.config.set("microphone_device", device_name)
            self._update_status(f"Mikrofon gewählt: {selected}")
    
    def _start_service(self):
        """Startet den Audio-Controller-Service"""
        if self.audio_controller.start():
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self._update_status("Service gestartet")
        else:
            messagebox.showwarning("Warnung", "Service läuft bereits")
    
    def _stop_service(self):
        """Stoppt den Audio-Controller-Service"""
        self.audio_controller.stop()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._update_status("Service gestoppt")
    
    def _save_config(self):
        """Speichert die Konfiguration"""
        self.config.save()
        self._update_status("Konfiguration gespeichert")
        messagebox.showinfo("Erfolg", "Konfiguration wurde gespeichert")
    
    def _reset_config(self):
        """Setzt Konfiguration auf Standardwerte zurück"""
        if messagebox.askyesno("Bestätigen", 
                               "Möchten Sie wirklich alle Einstellungen zurücksetzen?"):
            self.config.reset_to_defaults()
            self.config.save()
            self._update_status("Konfiguration zurückgesetzt")
            messagebox.showinfo("Info", "Bitte starten Sie die Anwendung neu, um die Standardwerte zu laden")
    
    def run(self):
        """Startet die GUI"""
        self._update_status("Gateway Auto-Mute gestartet")
        self.root.mainloop()
    
    def cleanup(self):
        """Räumt beim Beenden auf"""
        if self.audio_controller.is_running():
            self.audio_controller.stop()


def main():
    app = AutoMuteGUI()
    try:
        app.run()
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
