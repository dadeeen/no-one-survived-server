# No One Survived Dedicated Server — Docker

[English](README.md) · [Konfiguration](docs/CONFIGURATION.de.md) · [Wake & Sleep](docs/WAKE-AND-SLEEP.de.md) · [Netzwerk](docs/NETWORKING.de.md) · [Portainer](docs/PORTAINER.de.md) · [Backup](docs/BACKUP-RESTORE.de.md) · [Fehlerbehebung](docs/TROUBLESHOOTING.de.md) · [Lokale CI](docs/LOCAL-CI.de.md) · [Architektur](docs/ARCHITECTURE.de.md) · [Upstream](docs/UPSTREAM.de.md) · [Changelog](CHANGELOG.md) · [Sicherheit](SECURITY.de.md)

Ein Wine-/SteamCMD-Container für den Dedicated Server von **No One Survived**. Er installiert und aktualisiert den Server automatisch, hält Spielstände persistent, weckt bei einem erlaubten UDP-Paket und beendet den Gameserverprozess nach einer einstellbaren Leerlaufzeit.

> Dieses Projekt ist inoffiziell und steht in keiner Verbindung zu Cat Play Studio, Steam, Valve oder CubeCoders. Spiel- und Dedicated-Server-Dateien werden nicht weiterverteilt.
>
> **Validierungsstand**
>
> - Lokal erfolgreich geprüft: Installation und Update, Wine-Start, A2S-Antwort, UDP-Wake und sauberer Schlafzustand.
> - Noch nicht abschließend geprüft: Langzeitbetrieb, Spielstandpersistenz über Spielupdates hinweg und öffentliche Erreichbarkeit in unterschiedlichen Netztypen.

## Schnellstart mit Docker Compose

```bash
git clone https://github.com/dadeeen/no-one-survived-server.git
cd no-one-survived-server

cp .env.example .env

install -d -m 0700 secrets
printf '%s\n' 'server-passwort-waehlen' > secrets/server_password.txt
printf '%s\n' 'langes-zufaelliges-admin-passwort-waehlen' > secrets/admin_password.txt
chmod 0600 secrets/*.txt

docker compose -f compose.yaml -f compose.secrets.yaml up -d
docker compose logs -f
```

Beim ersten Start werden der Windows-Dedicated-Server heruntergeladen und Wine vorbereitet. Meldet `nosctl status` den Zustand `SLEEPING`, ist die Einrichtung abgeschlossen:

```bash
docker exec no-one-survived nosctl status
```

Das erste Verbindungspaket weckt den Server, kann den Beitritt aber nicht abschließen. Favorit oder Direktverbindung nach dem Serverstart erneut aufrufen, üblicherweise nach ungefähr 30–90 Sekunden.

## Schnellstart mit Portainer

1. Die beiden Passwortdateien wie in der [Portainer-Beispielanleitung](examples/README.de.md#1-passwortdateien-anlegen) erstellen.
2. Unter **Stacks → Add stack → Web editor** den Inhalt von [`examples/portainer-stack.yaml`](examples/portainer-stack.yaml) einfügen.
3. [`examples/portainer-stack.env.example`](examples/portainer-stack.env.example) unter **Environment variables** importieren.
4. Einen dauerhaften Stacknamen wählen und bereitstellen.

Die empfohlenen Dateien zeigen nur die Einstellungen für eine normale Installation. Für erweiterte Deployments stehen [`examples/portainer-stack.full.yaml`](examples/portainer-stack.full.yaml) und [`examples/portainer-stack.full.env.example`](examples/portainer-stack.full.env.example) bereit.

## Häufigste Einstellungen

Vor dem Deployment `.env` bearbeiten oder den Container nach einer Änderung neu erzeugen:

```env
SERVER_NAME=Mein NoS Server
MAX_PLAYERS=8
TZ=Europe/Berlin
IDLE_TIMEOUT_SECONDS=3600
WAKE_SOURCE_POLICY=private
```

Die empfohlene `.env.example` deckt den normalen Einstieg einschließlich des im Smoke-Test geprüften Xvfb-Wine-Pfads ab. Soll jede unterstützte Option sichtbar sein, stattdessen `.env.full.example` nach `.env` kopieren. Alle Beschreibungen stehen unter [Konfiguration](docs/CONFIGURATION.de.md).

## Funktionsweise von Wake-on-Packet

Im Schlafzustand bleibt der Container aktiv, aber `WRSHServer.exe` und Wine sind beendet. Ein kleiner Python-Listener belegt UDP-Port `7777` und/oder `27015`. Trifft ein erlaubtes Paket ein, schließt der Listener seine Sockets und startet den Gameserver.

Meldet der Server über den eingestellten Zeitraum null Spieler, wird er sauber beendet und der Listener erneut aktiviert. Die Standardrichtlinie `private` akzeptiert übliche private LAN-, Container- und geroutete VPN-Bereiche und lehnt öffentliche IPv4-Wake-Pakete ab. `allowlist` dient für explizite CIDRs; `any` nur für bewusst öffentliches Wake verwenden.

## Nützliche Befehle

```bash
# Zustand und Spielerzahl
docker exec no-one-survived nosctl status

# Manuell aufwecken
docker exec no-one-survived nosctl wake

# Gameserver sauber schlafen legen
docker exec no-one-survived nosctl sleep

# Container-Logs
docker compose logs -f
```

Alternativ stehen Signale zur Verfügung:

```bash
docker kill --signal SIGUSR1 no-one-survived  # aufwecken
docker kill --signal SIGUSR2 no-one-survived  # schlafen
```

## Persistente Verzeichnisstruktur

```text
/data/
├── server/       von SteamCMD installierter Dedicated Server
├── saved/        Spielstände, Logs, Game.ini und Engine.ini
├── wine/         Wine-Prefix, bei Bedarf neu erzeugbar
├── steamcmd/     selbst aktualisierende SteamCMD-Installation
├── state/        Update-/Wine-Marker und generiertes Admin-Passwort
├── home/         Home-Verzeichnis der Laufzeit
└── backups/      optionale lokale Sicherungsarchive
```

`/data/server/WRSH/Saved` verweist auf `/data/saved`. Dadurch ersetzen Serverupdates oder eine Neuinstallation nicht den persistenten Spielstandordner. `/data/saved` sollte zusätzlich außerhalb des Docker-Hosts gesichert werden.

## Netzwerk

Clients verbinden sich mit einer erreichbaren Adresse des Docker-Hosts, der VM oder des Container-Hosts. In gerouteten Netzen sind meist Direkt-IP oder Steam-Favorit erforderlich, da Broadcast-Erkennung Router normalerweise nicht überschreitet.

`WAKE_SOURCE_POLICY` steuert nur, wer einen schlafenden Server wecken darf; die Einstellung ist keine Firewall für den laufenden Server. Deployment-Beispiele und Hinweise zu öffentlichem Zugriff stehen unter [Netzwerk](docs/NETWORKING.de.md).

> **Öffentliche IPv4 / DS-Lite:** Erscheint der Server in der In-Game-Liste, der Beitritt bleibt aber im Ladebildschirm hängen oder läuft in einen Timeout, sollte geprüft werden, ob der Internetanschluss eine eigene öffentliche IPv4-Adresse besitzt. Bei DS-Lite/CGNAT kann die ausgehende Registrierung bei Steam funktionieren, während eingehender UDP-Verkehr auf den Ports `7777` und `27015` nicht durch das providerseitige NAT weitergeleitet wird. Eine Portfreigabe im Router allein reicht dann nicht; erforderlich kann eine öffentliche IPv4-/Dual-Stack-Option oder ein extern erreichbarer Tunnel beziehungsweise Relay sein. Dieses Verhalten ist für No One Survived noch nicht abschließend bestätigt und ist als Hinweis zur Fehlerdiagnose, nicht als bestätigte Einschränkung des Spiels zu verstehen.

## Lokal bauen

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.build.yaml build
```

Die Laufzeit wird direkt aus dem offiziellen Image `debian:trixie-slim`, den offiziellen stabilen WineHQ-Paketen der gewählten Wine-11-Linie und Valves SteamCMD-Bootstrap gebaut. AMP- oder CubeCoders-Laufzeitdateien sind nicht enthalten. Bei einer Veröffentlichung werden Debian-Digest, WineHQ-Paketversion und SteamCMD-Archivhash des geprüften Kandidaten aufgezeichnet und festgeschrieben; transitive APT-Pakete werden nicht über einen historischen Paket-Snapshot eingefroren.

## Validierungsstand

Das Repository enthält Tests für UDP-Wake, CIDR-Richtlinien, A2S-Auswertung, den erhaltenden INI-Merge, Secret-Validierung, die Parität der einfachen und vollständigen Deployment-Dateien, Update-Zeitsteuerung, Backup-/Restore-Sicherheit und die Invarianten des Laufzeitimages. Der Image-Build prüft zusätzlich amd64-/i386-Unterstützung, notwendige Laufzeitprogramme, den SteamCMD-Start und die Erstellung eines frischen Wine-Prefix.

Ist die gehostete Actions-Ausführung nicht verfügbar, lässt sich die vollständige reguläre Prüfung lokal aus PowerShell starten:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

Die optionalen Prüfungen mit echtem Gameserver und A2S sind unter [Lokale CI](docs/LOCAL-CI.de.md) beschrieben. Ein produktives Release sollte erst als validiert gelten, wenn der aktuelle Spielbuild auf einem Docker-Host hinsichtlich Start, A2S, sauberem Stop und persistierenden Spielständen geprüft wurde.

## Lizenz

Der Projektcode steht unter der MIT-Lizenz. Für Debian, Wine, SteamCMD und den Gameserver gelten jeweils deren eigene Lizenzen und Bedingungen.
