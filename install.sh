#!/bin/bash
# Installations-Skript für Gateway Auto-Mute

echo "=== Gateway Auto-Mute Installation ==="
echo ""

# Prüfe ob Python 3 installiert ist
if ! command -v python3 &> /dev/null; then
    echo "FEHLER: Python 3 ist nicht installiert"
    echo "Installieren Sie Python 3: sudo apt-get install python3 python3-pip"
    exit 1
fi

echo "Python 3 gefunden: $(python3 --version)"

# Prüfe ob pip installiert ist
if ! command -v pip3 &> /dev/null; then
    echo "FEHLER: pip3 ist nicht installiert"
    echo "Installieren Sie pip: sudo apt-get install python3-pip"
    exit 1
fi

echo "pip3 gefunden"

# Installiere System-Abhängigkeiten (optional, aber empfohlen)
echo ""
echo "Möchten Sie System-Abhängigkeiten installieren? (empfohlen)"
echo "Dies erfordert sudo-Rechte."
read -p "System-Abhängigkeiten installieren? (j/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[JjYy]$ ]]; then
    echo "Installiere System-Abhängigkeiten..."
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev python3-dev pulseaudio-utils
fi

# Erstelle virtuelle Umgebung
echo ""
echo "Erstelle virtuelle Python-Umgebung..."
if [ -d "venv" ]; then
    echo "Virtuelle Umgebung existiert bereits"
else
    python3 -m venv venv
    echo "Virtuelle Umgebung erstellt"
fi

# Aktiviere virtuelle Umgebung
echo "Aktiviere virtuelle Umgebung..."
source venv/bin/activate

# Installiere Python-Abhängigkeiten
echo ""
echo "Installiere Python-Abhängigkeiten..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Installation erfolgreich! ==="
    echo ""
    echo "Zum Starten der GUI:"
    echo "  source venv/bin/activate"
    echo "  python3 gui.py"
    echo ""
    echo "Oder direkt:"
    echo "  ./venv/bin/python3 gui.py"
    echo ""
    echo "Service-Verwaltung:"
    echo "  ./venv/bin/python3 service_manager.py start"
    echo "  ./venv/bin/python3 service_manager.py stop"
    echo "  ./venv/bin/python3 service_manager.py status"
    echo ""
else
    echo ""
    echo "FEHLER: Installation der Python-Abhängigkeiten fehlgeschlagen"
    echo "Versuchen Sie die manuelle Installation:"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi
