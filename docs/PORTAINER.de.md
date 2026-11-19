# Bereitstellung mit Portainer

[English](PORTAINER.md) · [Zurück zur README](../README.de.md) · [Konfigurationsreferenz](CONFIGURATION.de.md)

## Passwortdateien auf dem Docker-Host anlegen

Vor dem ersten Deployment die beiden Beispielpasswörter durch eigene, nicht leere Werte ersetzen. Verwendet der Stack andere Werte für `PUID` und `PGID`, die IDs auch in diesen Befehlen anpassen. Der Stack bindet die beiden Dateien schreibgeschützt ein.

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /opt/games/no-one-survived/secrets

printf '%s\n' 'ein-starkes-serverpasswort' \
  | sudo tee /opt/games/no-one-survived/secrets/server_password.txt >/dev/null
printf '%s\n' 'ein-langes-zufaelliges-adminpasswort' \
  | sudo tee /opt/games/no-one-survived/secrets/admin_password.txt >/dev/null

sudo chown 1000:1000 /opt/games/no-one-survived/secrets/*.txt
sudo chmod 0400 /opt/games/no-one-survived/secrets/*.txt
```

## Stack bereitstellen

Für ein privates GHCR-Paket vor dem Deployment `ghcr.io` als Registry hinterlegen. Zur Anmeldung dienen der GitHub-Benutzername und ein Token mit `read:packages`. Öffentliche Pakete sind ohne Anmeldung zugänglich.

1. In Portainer **Stacks → Add stack → Web editor** öffnen und die [Stack-Vorlage](../examples/portainer-stack.yaml) einfügen.
2. Einen dauerhaften Stacknamen wählen. Beim Namen `no-one-survived` liegen die Daten im Volume `no-one-survived_data`. Nach einer Umbenennung bindet Portainer ein neues, leeres Volume ein. Das bisherige Volume bleibt erhalten.
3. Unter `environment:` Zeitzone, Servername und Spielerlimit anpassen. Zahlen und boolesche Werte in Anführungszeichen setzen. Für eine feste Version in der Zeile `image:` den Tag `latest` durch den gewünschten Release-Tag ersetzen. Der Stack funktioniert ohne separate `.env`-Datei.
4. **Deploy the stack** wählen und das Containerprotokoll öffnen. Beim ersten Start lädt SteamCMD den Dedicated Server herunter und Wine bereitet den Start vor.

## Ersten Start prüfen

```bash
docker logs --tail 100 no-one-survived
docker exec no-one-survived nosctl status
```

Bei `SLEEPING` ist der Server bereit zum Aufwecken. Portainer zeigt den Container dabei als gesund an. Den Container weiterlaufen lassen, damit der UDP-Listener erreichbar bleibt. Der erste Verbindungsversuch weckt das Spiel. Sobald der Gameserver läuft, erneut verbinden.

## Image aktualisieren

Die Release Notes lesen, den Gameserver schlafen legen und ein [Backup außerhalb des Docker-Hosts sichern](BACKUP-RESTORE.de.md). Den Image-Tag im bestehenden Stack ändern und den Container mit demselben Stacknamen und Volume neu erstellen. Anschließend den Zustand mit `nosctl status` prüfen.

## Zweite Serverinstanz

Für die zweite Instanz einen eigenen Stacknamen wählen, damit sie ein eigenes Datenvolume erhält. Im Dienst `no-one-survived` den Containernamen und die UDP-Ports ersetzen. Die beiden Portvariablen im vorhandenen `environment:`-Block anpassen.

```yaml
container_name: no-one-survived-2
ports:
  - "7778:7778/udp"
  - "27016:27016/udp"
environment:
  GAME_PORT: "7778"
  QUERY_PORT: "27016"
```
