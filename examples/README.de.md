# Portainer-Stack-Beispiel

[English](README.md) · [Portainer-Dokumentation](../docs/PORTAINER.de.md) · [Konfigurationsreferenz](../docs/CONFIGURATION.de.md)

[`portainer-stack.yaml`](portainer-stack.yaml) ist das einzige Portainer-Beispiel. Es kann direkt in den Portainer-Webeditor eingefügt werden und enthält sinnvolle Standardwerte für eine normale Installation. Eine zusätzliche Env-Datei ist nicht erforderlich.

## 1. Passwortdateien anlegen

Das Beispiel verwendet UID und GID `1000`. Bei anderen IDs sowohl die Befehle als auch `PUID` und `PGID` im Stack anpassen.

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /opt/games/no-one-survived/secrets

printf '%s\n' 'ein-starkes-serverpasswort' \
  | sudo tee /opt/games/no-one-survived/secrets/server_password.txt >/dev/null
printf '%s\n' 'ein-langes-zufaelliges-adminpasswort' \
  | sudo tee /opt/games/no-one-survived/secrets/admin_password.txt >/dev/null

sudo chown 1000:1000 /opt/games/no-one-survived/secrets/*.txt
sudo chmod 0400 /opt/games/no-one-survived/secrets/*.txt
```

Beide Dateien müssen einen nicht leeren Wert enthalten. Leere Secret-Dateien werden abgelehnt.

## 2. Stack anlegen

1. **Stacks → Add stack → Web editor** öffnen.
2. [`portainer-stack.yaml`](portainer-stack.yaml) einfügen.
3. Die sichtbaren Werte direkt im YAML anpassen, insbesondere Image-Tag, Zeitzone, Servername und Spielerlimit.
4. Einen eindeutigen, dauerhaften Portainer-Stacknamen wählen.
5. Stack bereitstellen und das Containerprotokoll verfolgen.

Für ein privates GHCR-Package `ghcr.io` als Registry mit einem Token mit `read:packages` eintragen. Öffentliche Packages benötigen keine Registry-Zugangsdaten.

Das logische Volume heißt `data`. Portainer stellt den Stacknamen voran; ein Stack namens `no-one-survived` erzeugt daher normalerweise `no-one-survived_data`.

**Den Stacknamen nach dem ersten Deployment stabil halten.** Eine Umbenennung erzeugt ein neues leeres Volume; das alte bleibt vorhanden, wird aber nicht mehr automatisch eingebunden.

## 3. Was passiert danach?

Beim ersten Start werden der Dedicated Server heruntergeladen und Wine vorbereitet. Anschließend bleibt der Container im Zustand `SLEEPING`, bis ein erlaubtes UDP-Paket den Gameserver weckt.

```bash
docker exec no-one-survived nosctl status
docker logs -f no-one-survived
```

Das erste Verbindungspaket weckt den Server nur. Favorit oder Direktverbindung nach dem Start erneut aufrufen.

## Häufige Anpassungen

Die Werte direkt unter `environment:` ändern:

```yaml
environment:
  TZ: Europe/Berlin
  SERVER_NAME: Mein NoS Server
  MAX_PLAYERS: "8"
  IDLE_TIMEOUT_SECONDS: "3600"
  WAKE_SOURCE_POLICY: private
```

Für eine strikte Liste vertrauenswürdiger Netze:

```yaml
environment:
  WAKE_SOURCE_POLICY: allowlist
  WAKE_ALLOWED_NETWORKS: 192.168.10.0/24,10.50.0.0/24
```

`WAKE_SOURCE_POLICY: any` nur bewusst für öffentlich erreichbare UDP-Ports verwenden. Alle unterstützten optionalen Variablen stehen in der [Konfigurationsreferenz](../docs/CONFIGURATION.de.md); nur die benötigten Variablen zum vorhandenen `environment:`-Block ergänzen.

## Zweite Serverinstanz

Einen anderen dauerhaften Portainer-Stacknamen wählen und anschließend Containername sowie Hostports ändern:

```yaml
container_name: no-one-survived-2
ports:
  - "7778:7777/udp"
  - "27016:27015/udp"
```

Die internen Ports bleiben `7777` und `27015`. Portainer weist dem zweiten Stack automatisch ein eigenes benanntes Volume zu.

## Volume- und Image-Pflege

```bash
docker volume inspect no-one-survived_data
docker volume ls --filter name=no-one-survived
```

Das Volume bleibt bei einer Neuerstellung oder Aktualisierung des Containers erhalten. Es wird nur gelöscht, wenn es ausdrücklich entfernt wird, beispielsweise mit `docker volume rm`, `docker compose down -v` oder einer entsprechenden Portainer-Aktion. `/data/saved` sollte zusätzlich außerhalb des Docker-Hosts gesichert werden.

Das Beispiel verwendet der Einfachheit halber `latest`. Für stabilen Betrieb in der `image:`-Zeile einen getesteten Release-Tag wie `v0.1.0` eintragen.
