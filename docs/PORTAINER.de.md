# Bereitstellung mit Portainer

[English](PORTAINER.md) · [Zurück zur README](../README.de.md)

## Schnellstart

1. Die beiden nicht leeren Passwortdateien wie in der [Beispielanleitung](../examples/README.de.md#1-passwortdateien-anlegen) erstellen.
2. **Stacks → Add stack → Web editor** öffnen.
3. [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml) einfügen.
4. [`examples/portainer-stack.env.example`](../examples/portainer-stack.env.example) unter **Environment variables** importieren.
5. Einen eindeutigen, dauerhaften Stacknamen wählen und bereitstellen.
6. Die Erstinstallation mit `docker logs -f no-one-survived` verfolgen.

Beim ersten Deployment werden der Windows-Dedicated-Server heruntergeladen und Wine initialisiert. Meldet `nosctl status` den Zustand `SLEEPING`, ist die Einrichtung abgeschlossen. Das erste Verbindungspaket weckt den Server nur; nach dem Start erneut verbinden.

## Einfache und vollständige Beispiele

Das empfohlene Paar ist bewusst kurz und deckt eine normale Installation ab:

- [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml)
- [`examples/portainer-stack.env.example`](../examples/portainer-stack.env.example)

Für erweiterte Deployments stehen alle unterstützten Einstellungen bereit:

- [`examples/portainer-stack.full.yaml`](../examples/portainer-stack.full.yaml)
- [`examples/portainer-stack.full.env.example`](../examples/portainer-stack.full.env.example)

Beide Varianten verwenden dasselbe Image, dieselbe persistente Datenstruktur, schreibgeschützte Passwortdateien, die Stopfrist, die Sicherheitsoption und die Log-Rotation. Die vollständigen Dateien sind eine Referenz und für den normalen Betrieb nicht erforderlich.

Das `compose.yaml` im Repository-Stamm verwendet eine lokale `.env`-Datei und ist für Docker Compose gedacht. Im Portainer-Webeditor stattdessen die speziellen Beispiele verwenden.

## Zugriff auf die GHCR-Registry

Öffentliche GHCR-Packages können ohne Zugangsdaten geladen werden. Für ein privates Package `ghcr.io` in Portainer als Registry eintragen und einen GitHub-Personal-Access-Token mit `read:packages` verwenden; als Registry-Benutzer dient der GitHub-Benutzername.

Imagename:

```text
ghcr.io/dadeeen/no-one-survived-server:latest
```

Für stabilen Betrieb einen getesteten Release-Tag wie `v0.1.0` verwenden.

## Warum der Stack Kommentare enthält

Kommentare beschränken sich auf Verhalten, das aus dem Variablennamen nicht unmittelbar hervorgeht:

- der effektive Projekt-/Stackname bestimmt den persistenten Volume-Namen;
- die Stopfrist von 180 Sekunden lässt den vollständigen Wine-Shutdown zu;
- der Container bleibt in `SLEEPING` aktiv, damit der UDP-Wake-Listener erreichbar bleibt;
- Passwortdateien werden außerhalb des Stacks verwaltet und schreibgeschützt eingebunden.

Normale Variablennamen bleiben selbsterklärend. Ausführliche Beschreibungen stehen unter [Konfiguration](CONFIGURATION.de.md).

## Projektbezogenes Daten-Volume

Die mitgelieferten Stacks verwenden den logischen Volume-Namen `data`:

```yaml
name: ${STACK_NAME:-no-one-survived}

services:
  no-one-survived:
    volumes:
      - data:/data

volumes:
  data:
```

Compose stellt den **effektiven Projektnamen** voran. Beim Standardnamen erscheint das Docker-Volume normalerweise als `no-one-survived_data`.

Der Portainer-Stackname, `docker compose -p` und `COMPOSE_PROJECT_NAME` können den effektiven Projektnamen bestimmen oder überschreiben. Den Stack beziehungsweise das Projekt nach dem ersten Deployment nicht umbenennen. Ein neuer Name erzeugt ein neues leeres Volume; das bisherige Volume bleibt erhalten, wird aber nicht mehr automatisch eingebunden.

Für eine zweite Instanz einen anderen dauerhaften Stacknamen, Containernamen und andere Hostports verwenden. Das Volume wird automatisch getrennt.

## Betrieb in Portainer

Wird der Container gestoppt, ist auch automatisches Wake deaktiviert, weil kein Listener mehr läuft. Den Container üblicherweise im Zustand `SLEEPING` aktiv lassen und nur den Gameserverprozess schlafen lassen.

```bash
docker exec no-one-survived nosctl status
```

Portainer zeigt den Container im Schlafzustand als gesund an. Das ist beabsichtigt.

## Image aktualisieren

1. Release Notes und Änderung des Basisimages lesen.
2. `/data/saved` außerhalb des Containerhosts sichern.
3. Den getesteten Release-Tag in den Stackvariablen auswählen.
4. Den Container ohne Löschen des Volumes neu erzeugen.
5. Den Serverzustand mit `nosctl status` prüfen.

Wenn sich Wine ändert und `RESET_WINEPREFIX_ON_VERSION_CHANGE=true` gesetzt ist, wird der Prefix automatisch neu erzeugt. Spielstände und Spielkonfiguration verbleiben in `/data/saved`.
