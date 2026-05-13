#!/usr/bin/env python3
"""
Grafische Benutzeroberfläche für Gateway Auto-Mute
"""
import faulthandler
faulthandler.enable()  # Stacktrace bei SIGSEGV/SIGFPE ausgeben
import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
from pathlib import Path
import queue
import sys
from config import Config
from audio_controller import AudioController
from service_manager import ServiceManager


class ConfigSlider(ttk.Frame):
    """Benutzerdefinierter Schieberegler mit Min/Max-Textfeldern und optionalem Pegelanzeige-Balken"""

    def __init__(self, parent, label, config_key, config: Config,
                 min_key, max_key, unit="", on_change=None, show_level_meter=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.config_key = config_key
        self.min_key = min_key
        self.max_key = max_key
        self.on_change = on_change
        self.unit = unit
        self._meter_level = 0.0

        # row 0: Label
        ttk.Label(self, text=label).grid(row=0, column=0, columnspan=5, sticky=tk.W, pady=(5, 0))

        # row 1: Level-Meter Canvas (optional) ODER direkt der Slider-Bereich
        if show_level_meter:
            self.meter_canvas = tk.Canvas(self, height=18, bg='#1e1e1e',
                                          highlightthickness=1, highlightbackground='#555')
            self.meter_canvas.grid(row=1, column=0, columnspan=5, sticky=tk.EW, padx=0, pady=(2, 1))
            self.meter_canvas.bind('<Configure>', lambda e: self._draw_meter())
            slider_row = 2
            label_row = 3
        else:
            self.meter_canvas = None
            slider_row = 1
            label_row = 2

        # Min-Wert Eingabe
        ttk.Label(self, text="Min:").grid(row=slider_row, column=0, padx=(0, 5))
        self.min_var = tk.StringVar(value=str(config.get(min_key, 0)))
        min_entry = ttk.Entry(self, textvariable=self.min_var, width=8)
        min_entry.grid(row=slider_row, column=1, padx=(0, 10))
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
        self.slider.grid(row=slider_row, column=2, sticky=tk.EW, padx=5)
        self.columnconfigure(2, weight=1)

        # Max-Wert Eingabe
        ttk.Label(self, text="Max:").grid(row=slider_row, column=3, padx=(10, 5))
        self.max_var = tk.StringVar(value=str(config.get(max_key, 100)))
        max_entry = ttk.Entry(self, textvariable=self.max_var, width=8)
        max_entry.grid(row=slider_row, column=4)
        max_entry.bind('<FocusOut>', self._on_max_changed)
        max_entry.bind('<Return>', self._on_max_changed)

        # Aktueller Wert
        self.current_label = ttk.Label(self, text=f"{self.value_var.get():.1f} {unit}")
        self.current_label.grid(row=label_row, column=0, columnspan=5, sticky=tk.W)

    def update_level(self, level_percent: float):
        """Aktualisiert den angezeigten Audiopegel im Meter"""
        self._meter_level = level_percent
        self._draw_meter()

    def _draw_meter(self):
        """Zeichnet den Pegelanzeige-Balken neu"""
        if not self.meter_canvas:
            return
        w = self.meter_canvas.winfo_width()
        h = self.meter_canvas.winfo_height()
        if w <= 1:
            return

        try:
            min_val = float(self.min_var.get())
            max_val = float(self.max_var.get())
        except ValueError:
            return
        val_range = max_val - min_val if max_val != min_val else 1.0

        level = self._meter_level
        threshold = self.value_var.get()

        level_x = max(0, min(w, (level - min_val) / val_range * w))
        threshold_x = max(0, min(w - 1, (threshold - min_val) / val_range * w))

        self.meter_canvas.delete("all")

        # Hintergrund
        self.meter_canvas.create_rectangle(0, 0, w, h, fill='#1e1e1e', outline='')

        # Pegelbalken: grün wenn unter Schwellwert, rot wenn drüber
        if level_x > 0:
            color = '#4caf50' if level <= threshold else '#f44336'
            self.meter_canvas.create_rectangle(0, 2, level_x, h - 2, fill=color, outline='')

        # Schwellwert-Linie (gelb, gestrichelt)
        self.meter_canvas.create_line(threshold_x, 0, threshold_x, h,
                                      fill='#ffeb3b', width=2, dash=(3, 2))

        # Pegelwert als Text
        self.meter_canvas.create_text(w - 4, h // 2, anchor='e',
                                      text=f"{level:.0f}%", fill='white',
                                      font=('TkDefaultFont', 8))
    
    def _on_slider_changed(self, value):
        """Callback wenn Slider bewegt wird"""
        self.current_label.config(text=f"{float(value):.1f} {self.unit}")
        self.config.set(self.config_key, float(value))
        if self.on_change:
            self.on_change()
        self._draw_meter()
    
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
                if self.on_change:
                    self.on_change()
                self._draw_meter()
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
                if self.on_change:
                    self.on_change()
                self._draw_meter()
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
        self.root.geometry("1100x700")

        self.config = Config()
        self.unsaved_changes = False
        self._alive = True
        self._msg_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.audio_controller = AudioController(self.config, self._status_callback,
                                                self._level_callback)
        self._service_manager = ServiceManager()
        self._external_service = False   # True wenn Daemon-Prozess läuft
        self._log_file_pos = 0           # Leseposition im Service-Log

        self._create_widgets()
        self._load_devices()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_queue()
        self._check_external_service_status()  # Prüfe ob Daemon bereits läuft
        
    def _mark_dirty(self):
        """Markiert die Konfiguration als ungespeichert"""
        if not self.unsaved_changes:
            self.unsaved_changes = True
            self.root.title("Gateway Auto-Mute Konfiguration *")

    def _mark_clean(self):
        """Markiert die Konfiguration als gespeichert"""
        self.unsaved_changes = False
        self.root.title("Gateway Auto-Mute Konfiguration")

    def _on_close(self):
        """Behandelt das Schließen des Fensters"""
        if self.unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen.\nMöchten Sie diese vor dem Beenden speichern?"
            )
            if answer is None:  # Abbrechen
                return
            if answer:  # Ja
                self.config.save()
                self._mark_clean()
        # Reload-Nachfrage wenn ein Service läuft
        service_running = (self._external_service
                           or self.audio_controller.is_running())
        if service_running:
            if messagebox.askyesno(
                "Service neu laden",
                "Soll der laufende Service jetzt neu geladen werden,\n"
                "um Konfigurationsänderungen zu übernehmen?"
            ):
                self._reload_service()
        self._alive = False
        self.cleanup()
        self.root.destroy()

    def _level_callback(self, level: float):
        """Wird vom Background-Thread aufgerufen – nur Queue-Put, kein tkinter!"""
        self._msg_queue.put(('level', level))

    def _status_callback(self, message: str):
        """Wird vom Background-Thread aufgerufen – nur Queue-Put, kein tkinter!"""
        self._msg_queue.put(('status', message))

    def _poll_queue(self):
        """Läuft im Hauptthread; verarbeitet alle ausstehenden Nachrichten aus der Queue"""
        if not self._alive:
            return
        try:
            # Alle verfügbaren Nachrichten auf einmal verarbeiten
            while True:
                kind, value = self._msg_queue.get_nowait()
                if kind == 'level':
                    try:
                        self.volume_threshold_slider.update_level(value)
                    except tk.TclError:
                        pass
                elif kind == 'status':
                    self._update_status(value)
        except queue.Empty:
            pass
        finally:
            if self._alive:
                try:
                    self.root.after(50, self._poll_queue)
                except tk.TclError:
                    pass

    def _update_status(self, message: str):
        """Aktualisiert die Statusanzeige (nur aus Hauptthread aufrufen)"""
        if not self._alive:
            return
        try:
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, f"{message}\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        except tk.TclError:
            pass
    
    def _create_widgets(self):
        """Erstellt alle GUI-Elemente"""
        # Hauptcontainer mit Canvas und Scrollbar
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Canvas für Scrolling
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding="10")
        
        # Scrollbar konfigurieren
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Widgets platzieren
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame in Canvas einfügen
        canvas_frame = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Scrollregion aktualisieren wenn Frame sich ändert
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_frame, width=event.width)
        
        main_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Maus-Wheel-Support (Windows/macOS + Linux X11)
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        # Zwei Spalten: links 2/3, rechts 1/3
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=1)

        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_frame.columnconfigure(0, weight=1)

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        # ── LINKE SPALTE ──────────────────────────────────────────

        left_row = 0

        # === Service-Steuerung ===
        service_frame = ttk.LabelFrame(left_frame, text="Service-Steuerung", padding="10")
        service_frame.grid(row=left_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        left_row += 1

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

        # === Pegel und Schwellwerte ===
        levels_frame = ttk.LabelFrame(left_frame, text="Pegel und Schwellwerte", padding="10")
        levels_frame.grid(row=left_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        left_row += 1

        self.volume_threshold_slider = ConfigSlider(
            levels_frame,
            "Lautstärke-Schwellwert (ab diesem Pegel wird Mikrofon gedämpft)",
            "volume_threshold", self.config,
            "volume_threshold_min", "volume_threshold_max",
            unit="%", on_change=self._mark_dirty, show_level_meter=True
        )
        self.volume_threshold_slider.pack(fill=tk.X, pady=5)

        self.mic_normal_slider = ConfigSlider(
            levels_frame,
            "Normaler Mikrofon-Pegel",
            "mic_normal_level", self.config,
            "mic_normal_level_min", "mic_normal_level_max",
            unit="%", on_change=self._mark_dirty
        )
        self.mic_normal_slider.pack(fill=tk.X, pady=5)

        self.mic_muted_slider = ConfigSlider(
            levels_frame,
            "Gedämpfter Mikrofon-Pegel",
            "mic_muted_level", self.config,
            "mic_muted_level_min", "mic_muted_level_max",
            unit="%", on_change=self._mark_dirty
        )
        self.mic_muted_slider.pack(fill=tk.X, pady=5)

        # === Zeiteinstellungen ===
        time_frame = ttk.LabelFrame(left_frame, text="Zeiteinstellungen", padding="10")
        time_frame.grid(row=left_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        left_row += 1

        self.hold_time_slider = ConfigSlider(
            time_frame,
            "Haltezeit (Mikrofon bleibt gedämpft)",
            "hold_time", self.config,
            "hold_time_min", "hold_time_max",
            unit="ms", on_change=self._mark_dirty
        )
        self.hold_time_slider.pack(fill=tk.X, pady=5)

        self.polling_slider = ConfigSlider(
            time_frame,
            "Messintervall (min. 100ms) - Erfordert Neustart des Services",
            "polling_interval", self.config,
            "polling_interval_min", "polling_interval_max",
            unit="ms", on_change=self._mark_dirty
        )
        self.polling_slider.pack(fill=tk.X, pady=5)

        # === Geräteauswahl ===
        device_frame = ttk.LabelFrame(left_frame, text="Geräteauswahl", padding="10")
        device_frame.grid(row=left_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        left_row += 1

        ttk.Label(device_frame, text="Lautsprecher (Output):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.speaker_var = tk.StringVar(value=self.config.get("speaker_device", ""))
        self.speaker_combo = ttk.Combobox(device_frame, textvariable=self.speaker_var, width=40)
        self.speaker_combo.grid(row=0, column=1, padx=(10, 0), pady=5)
        self.speaker_combo.bind('<<ComboboxSelected>>', self._on_speaker_selected)

        ttk.Label(device_frame, text="Mikrofon (Input):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mic_var = tk.StringVar(value=self.config.get("microphone_device", ""))
        self.mic_combo = ttk.Combobox(device_frame, textvariable=self.mic_var, width=40)
        self.mic_combo.grid(row=1, column=1, padx=(10, 0), pady=5)
        self.mic_combo.bind('<<ComboboxSelected>>', self._on_mic_selected)

        ttk.Button(device_frame, text="Geräte aktualisieren",
                   command=self._load_devices).grid(row=2, column=0, columnspan=2, pady=(10, 0))

        # ── RECHTE SPALTE ─────────────────────────────────────────

        right_row = 0

        # === Status (füllt verfügbare Höhe) ===
        status_frame = ttk.LabelFrame(right_frame, text="Status", padding="10")
        status_frame.grid(row=right_row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        right_row += 1

        self.status_text = tk.Text(status_frame, height=16, width=1, state=tk.DISABLED, wrap=tk.WORD)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        status_scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=status_scrollbar.set)

        # === Service-Aktionen ===
        cmd_frame = ttk.LabelFrame(right_frame, text="Service-Aktionen", padding="10")
        cmd_frame.grid(row=right_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        right_row += 1

        actions = [
            ("Service starten",          self._start_service),
            ("Service stoppen",           self._stop_service),
            ("Service neu laden (reload)", self._reload_service),
            ("Service-Status anzeigen",   self._show_service_status),
        ]

        for label, cmd in actions:
            ttk.Button(cmd_frame, text=label, command=cmd).pack(
                fill=tk.X, pady=2)
    
    def _copy_to_clipboard(self, text: str):
        """Kopiert Text in die Zwischenablage"""
        try:
            pyperclip.copy(text)
            self._update_status(f"In Zwischenablage kopiert: {text}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte nicht in Zwischenablage kopieren: {e}")

    def _reload_service(self):
        """Stoppt und startet den laufenden Daemon-Service neu"""
        if self._external_service:
            self._update_status("Lade Service neu...")
            self._service_manager.restart()
        elif self.audio_controller.is_running():
            self._update_status("Lade Service neu...")
            self.audio_controller.stop()
            self.audio_controller.start()
            self._update_status("Service neu geladen")
        else:
            messagebox.showinfo("Info", "Service läuft nicht – nichts zu neu laden.")

    def _show_service_status(self):
        """Zeigt Daemon-Status im Status-Panel"""
        pid = self._service_manager._read_pid()
        running = self._service_manager._is_process_running(pid)
        if running:
            self._update_status(f"Daemon-Status: läuft (PID: {pid})")
        elif self.audio_controller.is_running():
            self._update_status("Daemon-Status: In-Process-Service läuft")
        else:
            self._update_status("Daemon-Status: gestoppt")
    
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
        
        # Gespeicherte Geräte in Combobox vorauswählen
        saved_speaker = self.config.get("speaker_device", "")
        for display_name, internal_name in self.speaker_map.items():
            if internal_name == saved_speaker:
                self.speaker_var.set(display_name)
                break
        
        saved_mic = self.config.get("microphone_device", "")
        for display_name, internal_name in self.mic_map.items():
            if internal_name == saved_mic:
                self.mic_var.set(display_name)
                break
    
    def _on_speaker_selected(self, event=None):
        """Callback wenn Lautsprecher ausgewählt wird"""
        selected = self.speaker_var.get()
        if selected in self.speaker_map:
            device_name = self.speaker_map[selected]
            self.config.set("speaker_device", device_name)
            self.config.save()
            self._update_status(f"Lautsprecher gewählt: {selected}")
    
    def _on_mic_selected(self, event=None):
        """Callback wenn Mikrofon ausgewählt wird"""
        selected = self.mic_var.get()
        if selected in self.mic_map:
            device_name = self.mic_map[selected]
            self.config.set("microphone_device", device_name)
            self.config.save()
            self._update_status(f"Mikrofon gewählt: {selected}")
    
    def _start_service(self):
        """Startet den Audio-Controller-Service"""
        if self._external_service:
            messagebox.showwarning("Warnung",
                                   "Ein externer Service läuft bereits.\n"
                                   "Bitte zuerst den externen Service stoppen.")
            return
        if self.audio_controller.start():
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            messagebox.showwarning("Warnung", "Service läuft bereits")

    def _stop_service(self):
        """Stoppt den Audio-Controller-Service"""
        if self._external_service:
            if messagebox.askyesno("Bestätigen",
                                   "Den extern laufenden Daemon-Service stoppen?"):
                self._service_manager.stop()
                # Button-Zustand wird durch _check_external_service_status aktualisiert
        else:
            self.audio_controller.stop()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
    
    def _save_config(self):
        """Speichert die Konfiguration"""
        self.config.save()
        self._mark_clean()
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
    
    def _check_external_service_status(self):
        """Prüft periodisch ob der Daemon-Service bereits läuft und verbindet das GUI damit"""
        if not self._alive:
            return
        pid = self._service_manager._read_pid()
        external_running = self._service_manager._is_process_running(pid)

        if external_running and not self._external_service:
            # Daemon wurde neu erkannt
            self._external_service = True
            self._update_status(f"Externer Service erkannt (PID: {pid}) – verbinde...")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            # Letzte Log-Zeilen als Kontext anzeigen, dann ab dort weiter lesen
            log_file = Path.home() / ".config" / "gateway-auto-mute" / "service.log"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        for line in lines[-5:]:
                            if line.strip():
                                self._update_status(f"[Log] {line.strip()}")
                        self._log_file_pos = log_file.stat().st_size
                except Exception:
                    self._log_file_pos = 0

        elif not external_running and self._external_service:
            # Daemon wurde gestoppt
            self._external_service = False
            self._update_status("Externer Service gestoppt")
            if not self.audio_controller.is_running():
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)

        if self._external_service:
            self._tail_log_file()

        self.root.after(2000, self._check_external_service_status)

    def _tail_log_file(self):
        """Liest neue Zeilen aus der Service-Log-Datei und zeigt sie im Status-Panel"""
        log_file = Path.home() / ".config" / "gateway-auto-mute" / "service.log"
        if not log_file.exists():
            return
        try:
            current_size = log_file.stat().st_size
            if current_size < self._log_file_pos:
                # Log-Datei wurde rotiert oder geleert
                self._log_file_pos = 0
            if current_size > self._log_file_pos:
                with open(log_file, 'r') as f:
                    f.seek(self._log_file_pos)
                    new_content = f.read()
                    self._log_file_pos = f.tell()
                for line in new_content.splitlines():
                    if line.strip():
                        self._update_status(line.strip())
        except Exception:
            pass

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
    app.run()


if __name__ == "__main__":
    main()
