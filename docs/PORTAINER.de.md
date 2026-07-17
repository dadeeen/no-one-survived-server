# Bereitstellung mit Portainer

[English](PORTAINER.md) · [Zurück zur README](../README.de.md) · [Konfigurationsreferenz](CONFIGURATION.de.md)

## Schnellstart

1. Die beiden nicht leeren Passwortdateien wie in der [Beispielanleitung](../examples/README.de.md#1-passwortdateien-anlegen) erstellen.
2. **Stacks → Add stack → Web editor** öffnen.
3. [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml) einfügen.
4. Die sichtbaren Werte direkt im YAML anpassen.
5. Einen eindeutigen, dauerhaften Stacknamen wählen und bereitstellen.
6. Die Erstinstallation mit `docker logs -f no-one-survived` verfolgen.

Eine zusätzliche Env-Datei ist nicht erforderlich. Der Stack enthält die üblichen Einstellungen für eine normale Installation. Optionale Variablen aus der [Konfigurationsreferenz](CONFIGURATION.de.md) nur bei Bedarf ergänzen.

Beim ersten Deployment werden der Windows-Dedicated-Server heruntergeladen und Wine initialisiert. Meldet `nosctl status` den Zustand `SLEEPING`, ist die Einrichtung abgeschlossen. Das erste Verbindungspaket weckt den Server nur; nach dem Start erneut verbinden.

## Zugriff auf die GHCR-Registry

Öffentliche GHCR-Packages können ohne Zugangsdaten geladen werden. Für ein privates Package `ghcr.io` in Portainer als Registry eintragen und einen GitHub-Personal-Access-Token mit `read:packages` verwenden; als Registry-Benutzer dient der GitHub-Benutzername.

Imagename:

```text
ghcr.io/dadeeen/no-one-survived-server:latest
```

Für stabilen Betrieb `latest` im Stack durch einen getesteten Release-Tag wie `v0.1.0` ersetzen.

## Stack bearbeiten

Das Beispiel verwendet bewusst direkte Werte statt `${VARIABLE}`-Platzhaltern. Häufige Einstellungen werden an Ort und Stelle geändert:

```yaml
environment:
  TZ: Europe/Berlin
  SERVER_NAME: Mein NoS Server
  MAX_PLAYERS: "8"
  IDLE_TIMEOUT_SECONDS: "3600"
```

Optionale Einstellungen lassen sich zum selben `environment:`-Block hinzufügen. Boolesche und numerische Werte sollten in YAML in Anführungszeichen stehen, damit ihre Übergabe als Zeichenfolge eindeutig ist.

Die Kommentare beschränken sich auf Verhalten, das aus dem Einstellungsnamen nicht unmittelbar hervorgeht:

- der Portainer-Stackname bestimmt den persistenten Volume-Namen;
- die Stopfrist von 180 Sekunden lässt den vollständigen Wine-Shutdown zu;
- der Container bleibt in `SLEEPING` aktiv, damit der UDP-Wake-Listener erreichbar bleibt;
- Passwortdateien werden außerhalb des Stacks verwaltet und schreibgeschützt eingebunden.

## Projektbezogenes Daten-Volume

Der mitgelieferte Stack verwendet den logischen Volume-Namen `data`:

```yaml
services:
  no-one-survived:
    volumes:
      - data:/data

volumes:
  data:
```

Portainer stellt den Stacknamen voran. Ein Stack namens `no-one-survived` erzeugt normalerweise das Docker-Volume `no-one-survived_data`.

Den Stack nach dem ersten Deployment nicht umbenennen. Ein neuer Name erzeugt ein neues leeres Volume; das bisherige Volume bleibt erhalten, wird aber nicht mehr automatisch eingebunden.

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
3. Den Tag in der `image:`-Zeile des Stacks durch den getesteten Release-Tag ersetzen.
4. Den Container ohne Löschen des Volumes neu erzeugen.
5. Den Serverzustand mit `nosctl status` prüfen.

Wenn sich Wine ändert und `RESET_WINEPREFIX_ON_VERSION_CHANGE=true` gesetzt ist, wird der Prefix automatisch neu erzeugt. Spielstände und Spielkonfiguration verbleiben in `/data/saved`.
