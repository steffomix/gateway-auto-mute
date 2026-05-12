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
        self._level_update_pending = False
        self._pending_level = 0.0
        self.audio_controller = AudioController(self.config, self._status_callback,
                                                self._level_callback)
        
        self._create_widgets()
        self._load_devices()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
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
        self._alive = False
        self.cleanup()
        self.root.destroy()

    def _level_callback(self, level: float):
        """Callback für Audiopegel-Updates vom Controller (thread-safe, gedrosselt)"""
        self._pending_level = level
        if not self._level_update_pending:
            self._level_update_pending = True
            try:
                self.root.after(50, self._apply_level_update)
            except tk.TclError:
                pass

    def _apply_level_update(self):
        """Wendet den zuletzt gemessenen Pegel auf den Meter an"""
        self._level_update_pending = False
        if not self._alive:
            return
        try:
            self.volume_threshold_slider.update_level(self._pending_level)
        except tk.TclError:
            pass

    def _status_callback(self, message: str):
        """Callback für Statusmeldungen"""
        if not self._alive:
            return
        try:
            self.root.after(0, lambda: self._update_status(message))
        except tk.TclError:
            pass
    
    def _update_status(self, message: str):
        """Aktualisiert die Statusanzeige"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
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
            "Messintervall (min. 10ms)",
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

        # === Kommandos für Terminal ===
        cmd_frame = ttk.LabelFrame(right_frame, text="Kommandos für Terminal", padding="10")
        cmd_frame.grid(row=right_row, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        cmd_frame.columnconfigure(1, weight=1)
        right_row += 1

        script_path = Path(__file__).parent / "service_manager.py"

        commands = [
            ("Service starten:", f"python3 {script_path} start"),
            ("Service stoppen:", f"python3 {script_path} stop"),
            ("Service-Status:", f"python3 {script_path} status"),
            ("Konfiguration anzeigen:", f"python3 {script_path} config"),
        ]

        for i, (label, cmd) in enumerate(commands):
            ttk.Label(cmd_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            cmd_entry = ttk.Entry(cmd_frame, width=1)
            cmd_entry.insert(0, cmd)
            cmd_entry.config(state='readonly')
            cmd_entry.grid(row=i, column=1, padx=(10, 5), pady=2, sticky=tk.EW)

            ttk.Button(cmd_frame, text="Kopieren",
                      command=lambda c=cmd: self._copy_to_clipboard(c)).grid(row=i, column=2, pady=2)
    
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
        if self.audio_controller.start():
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            messagebox.showwarning("Warnung", "Service läuft bereits")
    
    def _stop_service(self):
        """Stoppt den Audio-Controller-Service"""
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
