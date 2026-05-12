# Gateway Auto-Mute

Ein Python-Programm zur automatischen Mikrofon-Dämpfung für CB-Funk-Gateways, das Audio-Rückkopplungen verhindert.

## Beschreibung

Gateway Auto-Mute ist ein Hintergrund-Service mit grafischer Benutzeroberfläche, der die Empfindlichkeit eines Mikrofon-Eingangs automatisch herunterregelt, wenn Audio über eine Lautsprecher-Soundkarte ausgegeben wird. Dies verhindert unerwünschte Rückkopplungen bei CB-Funk-Gateway-Setups mit Teamspeak oder CB-Funkgeräten.

### Hauptfunktionen

- **Automatische Mikrofon-Dämpfung**: Reduziert Mikrofon-Empfindlichkeit bei Lautsprecher-Aktivität
- **Konfigurierbare Schwellwerte**: Alle Pegel und Zeitwerte sind über Schieberegler einstellbar
- **Flexible Geräteauswahl**: Wählen Sie beliebige PulseAudio-Soundkarten
- **Hintergrund-Service**: Läuft als Daemon im Hintergrund
- **GUI-Konfiguration**: Benutzerfreundliche grafische Oberfläche für alle Einstellungen
- **Robuste Fehlerbehandlung**: Funktioniert auch wenn Geräte temporär nicht verfügbar sind
- **Idle-Modus**: Pausiert automatisch wenn Geräte stumm geschaltet sind

## Systemanforderungen

- Linux mit PulseAudio
- Python 3.8 oder höher
- pip (Python Package Manager)

## Installation

1. **Repository klonen oder herunterladen**
   ```bash
   cd ~/Dokumente/Coding/Python/Gateway-auto-mute
   ```

2. **Abhängigkeiten installieren**
   ```bash
   pip install -r requirements.txt
   ```
   
   Oder mit virtualenv (empfohlen):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Skripte ausführbar machen**
   ```bash
   chmod +x gui.py service_manager.py install.sh
   ```

   Oder verwenden Sie das Installations-Skript:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

## Verwendung

### Grafische Benutzeroberfläche starten

```bash
python3 gui.py
```

oder wenn executable gemacht:
```bash
./gui.py
```

### GUI-Funktionen

1. **Geräteauswahl**
   - Wählen Sie Ihre Lautsprecher-Soundkarte (Output)
   - Wählen Sie Ihre Mikrofon-Soundkarte (Input)
   - Klicken Sie "Geräte aktualisieren" um die Liste zu aktualisieren

2. **Pegel und Schwellwerte konfigurieren**
   - **Lautstärke-Schwellwert**: Ab diesem Pegel wird das Mikrofon gedämpft (0-100%)
   - **Normaler Mikrofon-Pegel**: Empfindlichkeit im Normalbetrieb (0-100%)
   - **Gedämpfter Mikrofon-Pegel**: Reduzierte Empfindlichkeit bei Aktivität (0-100%)
   - Min/Max-Werte können über Textfelder angepasst werden

3. **Zeiteinstellungen**
   - **Haltezeit**: Wie lange das Mikrofon gedämpft bleibt (in ms)
   - **Messintervall**: Wie oft die Lautstärke gemessen wird (min. 10ms)

4. **Service-Steuerung**
   - **Service starten**: Startet die Überwachung in der GUI
   - **Service stoppen**: Stoppt die Überwachung
   - **Konfiguration speichern**: Speichert alle Einstellungen dauerhaft
   - **Zurücksetzen**: Setzt auf Standardwerte zurück

5. **Kommandos kopieren**
   - Kopieren Sie Befehle für die Terminal-Steuerung in die Zwischenablage

### Service über Terminal steuern

#### Service im Hintergrund starten
```bash
python3 service_manager.py start
```

#### Service stoppen
```bash
python3 service_manager.py stop
```

#### Service-Status anzeigen
```bash
python3 service_manager.py status
```

#### Konfiguration anzeigen
```bash
python3 service_manager.py config
```

#### Service neu starten
```bash
python3 service_manager.py restart
```

## Konfigurationsdatei

Die Konfiguration wird automatisch gespeichert in:
```
~/.config/gateway-auto-mute/config.json
```

Die PID-Datei des laufenden Services befindet sich in:
```
~/.config/gateway-auto-mute/service.pid
```

Service-Logs werden geschrieben nach:
```
~/.config/gateway-auto-mute/service.log
```

## Funktionsweise

1. Das Programm überwacht kontinuierlich die Lautstärke der ausgewählten Lautsprecher-Soundkarte
2. Wenn die Lautstärke den konfigurierten Schwellwert überschreitet:
   - Die Mikrofon-Empfindlichkeit wird auf den gedämpften Pegel reduziert
3. Die Dämpfung bleibt für die konfigurierte Haltezeit aktiv
4. Danach wird die Mikrofon-Empfindlichkeit wieder auf den Normalpegel gesetzt
5. Wenn eines der Geräte stumm geschaltet ist, geht das Programm in den Idle-Modus

## Fehlerbehebung

### Geräte werden nicht gefunden
- Stellen Sie sicher, dass PulseAudio läuft: `pulseaudio --check`
- Prüfen Sie verfügbare Geräte: `pactl list sinks` und `pactl list sources`
- Klicken Sie auf "Geräte aktualisieren" in der GUI

### Service startet nicht
- Prüfen Sie die Log-Datei: `cat ~/.config/gateway-auto-mute/service.log`
- Stellen Sie sicher, dass keine andere Instanz läuft: `python3 service_manager.py status`

### Mikrofon wird nicht gedämpft
- Überprüfen Sie die Schwellwerte in der Konfiguration
- Stellen Sie sicher, dass beide Geräte nicht stumm geschaltet sind
- Überprüfen Sie die Log-Ausgabe im Status-Fenster der GUI

### Abhängigkeiten installieren schlägt fehl
- Installieren Sie PortAudio: `sudo apt-get install portaudio19-dev python3-dev`
- Bei Ubuntu/Debian: `sudo apt-get install python3-pyaudio`

## Projektstruktur

```
Gateway-auto-mute/
├── config.py              # Konfigurationsverwaltung
├── audio_controller.py    # Audio-Überwachung und -Steuerung
├── gui.py                 # Grafische Benutzeroberfläche
├── service_manager.py     # Service-Verwaltung (Daemon)
├── main.py                # Haupteinstiegspunkt
├── install.sh             # Installations-Skript
├── requirements.txt       # Python-Abhängigkeiten
└── README.md              # Diese Datei
```

## Lizenz

Siehe LICENSE-Datei für Details.

## Beitragen

Fehlerberichte und Pull Requests sind willkommen!
