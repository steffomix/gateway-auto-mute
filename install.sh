#!/bin/bash
# Installations-Skript für Gateway Auto-Mute
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_NAME="gateway-auto-mute"
SERVICE_DST="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

echo "=== Gateway Auto-Mute Installation ==="
echo "Installationsverzeichnis: $INSTALL_DIR"
echo ""

# ── Python 3 prüfen ────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "FEHLER: Python 3 ist nicht installiert."
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-venv"
    echo "  Fedora:         sudo dnf install python3"
    echo "  Arch:           sudo pacman -S python"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "Python $PY_VERSION gefunden: $(which python3)"

# Python-Version >= 3.8 verlangen
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)'; then
    echo "Python-Version OK."
else
    echo "FEHLER: Python 3.8 oder neuer wird benötigt (gefunden: $PY_VERSION)."
    exit 1
fi

# ── python3-venv prüfen ────────────────────────────────────────
if ! python3 -m venv --help &> /dev/null; then
    echo "FEHLER: python3-venv ist nicht installiert."
    echo "  Ubuntu/Debian:  sudo apt install python3-venv"
    exit 1
fi

# ── System-Abhängigkeiten ──────────────────────────────────────
echo ""
echo "System-Abhängigkeiten werden benötigt:"
echo "  python3-tk      – grafische Oberfläche (tkinter)"
echo "  pulseaudio-utils – pactl/parec für Audio-Überwachung"
echo "  xclip oder xsel  – Zwischenablage (für pyperclip)"
echo ""
read -p "System-Abhängigkeiten jetzt installieren? (empfohlen) [J/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if command -v apt-get &> /dev/null; then
        echo "Installiere via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y python3-tk pulseaudio-utils xclip
    elif command -v dnf &> /dev/null; then
        echo "Installiere via dnf..."
        sudo dnf install -y python3-tkinter pulseaudio-utils xclip
    elif command -v pacman &> /dev/null; then
        echo "Installiere via pacman..."
        sudo pacman -S --noconfirm tk pulseaudio xclip
    else
        echo "WARNUNG: Unbekannte Paketverwaltung."
        echo "Bitte installieren Sie manuell: python3-tk, pulseaudio-utils, xclip"
    fi
fi

# Tkinter-Verfügbarkeit prüfen
if ! python3 -c 'import tkinter' 2>/dev/null; then
    echo ""
    echo "WARNUNG: tkinter ist nicht verfügbar – die GUI wird nicht starten."
    echo "  Ubuntu/Debian: sudo apt install python3-tk"
fi

# ── Virtuelle Umgebung erstellen ───────────────────────────────
echo ""
if [ -d "$VENV_DIR" ]; then
    echo "Virtuelle Umgebung existiert bereits ($VENV_DIR)."
else
    echo "Erstelle virtuelle Python-Umgebung..."
    python3 -m venv "$VENV_DIR"
    echo "Virtuelle Umgebung erstellt."
fi

# ── Python-Abhängigkeiten installieren ────────────────────────
echo ""
echo "Installiere Python-Abhängigkeiten..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo "Python-Abhängigkeiten installiert."

# ── Skripte ausführbar machen ─────────────────────────────────
chmod +x "$INSTALL_DIR/start.sh"
chmod +x "$INSTALL_DIR/install.sh"
echo ""
echo "start.sh ist ausführbar."

# ── Systemd User-Service einrichten ───────────────────────────
echo ""
if command -v systemctl &> /dev/null; then
    read -p "Systemd User-Service installieren und aktivieren? [J/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        # Service-Datei mit korrekten Pfaden generieren
        mkdir -p "$(dirname "$SERVICE_DST")"
        cat > "$SERVICE_DST" << EOF
[Unit]
Description=Gateway Auto-Mute Service
After=sound.target pulseaudio.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${INSTALL_DIR}/service_manager.py _daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable "$SERVICE_NAME"
        systemctl --user start  "$SERVICE_NAME"
        echo "Systemd User-Service installiert, aktiviert und gestartet."
        echo "  Status:  systemctl --user status $SERVICE_NAME"
        echo "  Logs:    journalctl --user -u $SERVICE_NAME -f"
    fi
else
    echo "systemctl nicht gefunden – Systemd-Service übersprungen."
fi

# ── Zusammenfassung ────────────────────────────────────────────
echo ""
echo "=== Installation abgeschlossen! ==="
echo ""
echo "GUI starten:"
echo "  $INSTALL_DIR/start.sh"
echo ""
echo "Service manuell steuern:"
echo "  $VENV_DIR/bin/python3 $INSTALL_DIR/service_manager.py start"
echo "  $VENV_DIR/bin/python3 $INSTALL_DIR/service_manager.py stop"
echo "  $VENV_DIR/bin/python3 $INSTALL_DIR/service_manager.py status"
