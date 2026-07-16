# Empfohlener Portainer-Stack

[English](README.md) · [Portainer-Dokumentation](../docs/PORTAINER.de.md)

Das empfohlene Portainer-Paar ist bewusst kurz:

- [`portainer-stack.yaml`](portainer-stack.yaml)
- [`portainer-stack.env.example`](portainer-stack.env.example)

Es enthält das persistente Daten-Volume, schreibgeschützte Passwortdateien, sichere Wake-/Sleep-Standards, eine ausreichende Stopfrist, Log-Rotation und `no-new-privileges`. Das erweiterte Paar zeigt alle unterstützten Einstellungen:

- [`portainer-stack.full.yaml`](portainer-stack.full.yaml)
- [`portainer-stack.full.env.example`](portainer-stack.full.env.example)

## 1. Passwortdateien anlegen

Die Beispiele verwenden UID und GID `1000`. Bei anderen IDs die Befehle und Stackvariablen entsprechend anpassen.

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

1. **Stacks → Add stack → Web editor** öffnen und `portainer-stack.yaml` einfügen.
2. Einen eindeutigen, dauerhaften Portainer-Stacknamen wählen.
3. `portainer-stack.env.example` unter **Environment variables** importieren.
4. Bei privatem GHCR-Package `ghcr.io` als Registry mit einem Token mit `read:packages` eintragen.
5. Stack bereitstellen und das Containerprotokoll verfolgen.

Das logische Volume heißt im Stack `data`. Compose beziehungsweise Portainer ergänzt den effektiven Projekt-/Stacknamen. Beim Standardnamen entsteht normalerweise `no-one-survived_data`.

**Den effektiven Projekt-/Stacknamen nach dem ersten Deployment stabil halten.** Eine Umbenennung erzeugt ein neues leeres Volume; das alte bleibt erhalten, wird aber nicht mehr automatisch eingebunden.

## 3. Was passiert danach?

Beim ersten Start werden der Dedicated Server heruntergeladen und Wine vorbereitet. Anschließend bleibt der Container im Zustand `SLEEPING`, bis ein erlaubtes UDP-Paket den Gameserver weckt.

```bash
docker exec no-one-survived nosctl status
docker logs -f no-one-survived
```

Das erste Verbindungspaket weckt den Server nur. Favorit oder Direktverbindung nach dem Start erneut aufrufen.

## Häufigste Anpassungen

```env
SERVER_NAME=Mein NoS Server
MAX_PLAYERS=8
TZ=Europe/Berlin
IDLE_TIMEOUT_SECONDS=3600
WAKE_SOURCE_POLICY=private
```

Für eine strikte Liste vertrauenswürdiger Netze:

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

`WAKE_SOURCE_POLICY=any` nur bewusst für öffentlich erreichbare UDP-Ports verwenden.

## Erweiterte Konfiguration

Den `.full`-Stack und die vollständige Env-Vorlage verwenden, wenn Update-Zeitsteuerung, A2S-Tuning, Wine-Kompatibilität, Crash-Recovery oder erweiterte Spieleinstellungen direkt in Portainer sichtbar sein sollen. Einfache und vollständige Variante verwenden dasselbe persistente Volume- und Passwortdateikonzept.

## Zweite Serverinstanz

Portainer-Projekt-/Stackname, Containername und Hostports müssen eindeutig sein:

```env
STACK_NAME=no-one-survived-2
CONTAINER_NAME=no-one-survived-2
GAME_PORT=7778
QUERY_PORT=27016
```

Compose erzeugt für den zweiten Stack normalerweise `no-one-survived-2_data`.

## Volume- und Image-Pflege

```bash
docker volume inspect no-one-survived_data
docker volume ls --filter name=no-one-survived
```

Das Volume bleibt bei einer Neuerstellung oder Aktualisierung des Containers erhalten. Es wird nur gelöscht, wenn es ausdrücklich entfernt wird, beispielsweise mit `docker volume rm`, `docker compose down -v` oder einer entsprechenden Portainer-Aktion. `/data/saved` sollte zusätzlich außerhalb des Docker-Hosts gesichert werden.

`IMAGE_TAG=latest` ist während der Entwicklung praktisch. Für stabilen Betrieb einen getesteten Release-Tag wie `v0.1.0` verwenden.
