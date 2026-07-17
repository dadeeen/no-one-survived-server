# Konfigurationsreferenz

[English](CONFIGURATION.md) · [Zurück zur README](../README.de.md)

Die Werte werden über Umgebungsvariablen übergeben. Boolesche Werte akzeptieren `true/false`, `1/0`, `yes/no` und `on/off`. Die empfohlene `.env.example` und der direkt einsetzbare Portainer-Stack enthalten die üblichen Einstellungen für eine normale Installation. Alle weiteren Variablen können für Docker Compose zu `.env` oder in Portainer zum vorhandenen `environment:`-Block ergänzt werden.

## Docker-Compose-Einstellungen

| Variable | Standard | Bedeutung |
|---|---:|---|
| `TZ` | `UTC` | Zeitzone des Containers, zum Beispiel `Europe/Berlin`. |
| `STACK_NAME` | `no-one-survived` | Effektiver Compose-Projektname und Präfix des `data`-Volumes. Nach dem ersten Deployment stabil halten. |
| `IMAGE_TAG` | `latest` | GHCR-Image-Tag. Für stabilen Betrieb einen getesteten Release-Tag verwenden. |
| `CONTAINER_NAME` | `no-one-survived` | Expliziter Containername. Muss sich zwischen Instanzen unterscheiden. |
| `HOST_BIND_ADDRESS` | `0.0.0.0` | Hostadresse für die beiden veröffentlichten UDP-Ports. |
| `STOP_GRACE_PERIOD` | `180s` | Docker-Stopfrist. Sie ist länger als der vollständige interne Eskalationspfad beim Beenden. |
| `LOG_MAX_SIZE` / `LOG_MAX_FILES` | `10m` / `3` | Rotation des Docker-Logtreibers `json-file`. |

In Portainer werden die entsprechenden Image-, Container-, Port-, Stopfrist- und Logging-Werte direkt in `examples/portainer-stack.yaml` geändert. Der Portainer-Stackname bestimmt das Präfix des benannten Volumes.

## Lebenszyklus und Updates

| Variable | Standard | Bedeutung |
|---|---:|---|
| `PREPARE_ON_CONTAINER_START` | `true` | SteamCMD, Wine und Konfiguration vor dem Anfangszustand vorbereiten. |
| `START_SERVER_ON_CONTAINER_START` | `false` in `compose.yaml` | Gameserver sofort starten. Bei `false` wird nach der Vorbereitung auf UDP-Wake gewartet. |
| `UPDATE_ON_CONTAINER_START` | `true` | SteamCMD beim Containerstart ausführen. Ein fehlender Server wird immer installiert. |
| `UPDATE_ON_WAKE` | `false` | Vor jedem Aufwecken SteamCMD ausführen; erhöht die Wake-Latenz. |
| `UPDATE_INTERVAL_SECONDS` | `0` | Periodisches Updateintervall im Schlafzustand; `0` deaktiviert es. |
| `UPDATE_RETRY_DELAY_SECONDS` | `900` | Wartezeit vor einem neuen Versuch nach fehlgeschlagener Erstvorbereitung oder einem periodischen Update. Die Erstvorbereitung bleibt im Container und erzeugt keine schnelle Docker-Neustartschleife. |
| `STEAMCMD_TIMEOUT_SECONDS` | `3600` | Maximale Gesamtlaufzeit eines SteamCMD-Updateversuchs. |
| `VALIDATE_ON_UPDATE` | `false` | `validate` an SteamCMD übergeben. Zur Reparatur, nicht für jeden Normalstart. |
| `START_ON_UPDATE_FAILURE` | `false` | Vorhandene Serverdateien trotz eines nicht zwingenden Updatefehlers starten. Eine fehlende Erstinstallation bleibt gesperrt und wird nach `UPDATE_RETRY_DELAY_SECONDS` erneut versucht. |
| `RESTART_ON_CRASH` | `true` | Unerwartet beendeten Gameserver neu starten. |
| `CRASH_RESTART_DELAY_SECONDS` | `15` | Wartezeit vor einem Crash-Neustart. |
| `MAX_CRASH_RESTARTS` | `3` | Maximale Anzahl aufeinanderfolgender automatischer Crash-Neustarts. |
| `CRASH_RESTART_RESET_SECONDS` | `600` | Setzt den Crash-Zähler nach dieser stabilen Laufzeit zurück; `0` deaktiviert das Zurücksetzen. |

Schlägt die anfängliche SteamCMD- oder Wine-Vorbereitung fehl, schreibt der Supervisor den Zustand `ERROR`, bleibt aktiv und versucht es nach der konfigurierten Wartezeit erneut. Dadurch wird `restart: unless-stopped` bei einem vorübergehenden Upstream-Ausfall nicht zu einer schnellen Container-Neustartschleife. Konfigurationsfehler brechen weiterhin sofort ab und müssen vor einem erneuten Erstellen oder Starten des Containers behoben werden.

## Wake-on-Packet

| Variable | Standard | Bedeutung |
|---|---:|---|
| `WAKE_ON_GAME_PORT` | `true` | Im Schlafzustand auf `GAME_PORT` lauschen. |
| `WAKE_ON_QUERY_PORT` | `true` | Im Schlafzustand auf `QUERY_PORT` lauschen. |
| `WAKE_BIND_ADDRESS` | `0.0.0.0` | Lokale IPv4-Adresse des Schlaf-Listeners. |
| `WAKE_SOURCE_POLICY` | `private` | `private`, `allowlist` oder `any`; steuert, welche IPv4-Quellen den Server wecken dürfen. |
| `WAKE_ALLOWED_NETWORKS` | leer | Optionale kommagetrennte IPv4-CIDRs. Ergänzen `private`, sind für `allowlist` erforderlich und bei `any` für die Wake-Entscheidung ohne Wirkung. |
| `WAKE_PACKET_COUNT` | `1` | Benötigte Pakete derselben Quell-IP innerhalb des Zeitfensters. Ein höherer Wert reduziert versehentliche Starts. |
| `WAKE_PACKET_WINDOW_SECONDS` | `5` | Zeitfenster für `WAKE_PACKET_COUNT`. |
| `WAKE_ARM_DELAY_SECONDS` | `5` | Verzögerung nach dem Stop, bevor Wake-Pakete akzeptiert werden; verhindert sofortiges Wiederaufwecken durch alten Traffic. |
| `WAKE_IGNORE_EMPTY_PACKETS` | `true` | UDP-Datagramme ohne Nutzdaten ignorieren. |

Das erste akzeptierte Paket weckt den Server, wird aber nicht erneut an ihn zugestellt. Der Client muss nach dem Start erneut verbinden. Die Pakethistorie wird zeitbasiert bereinigt und begrenzt, damit viele Quelladressen kein unbegrenztes Speicherwachstum verursachen. Im Schlafzustand bleiben die UDP-Sockets über die Abfrageintervalle hinweg gebunden; es gibt kein absichtliches Schließen und erneutes Öffnen im Fünf-Sekunden-Takt.

Empfohlener Standard:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
WAKE_PACKET_COUNT=1
```

`private` enthält RFC1918-LAN-Bereiche, Docker-Bridge-Netze, `100.64.0.0/10` für Overlay-Netze und Loopback. `allowlist` ist für eine strikte CIDR-Auswahl gedacht. `any` nur verwenden, wenn öffentliches Wake beabsichtigt ist. Die Richtlinie steuert nur das Aufwecken und ersetzt weder Firewall noch Serverpasswort.

Für ausschließlich manuelles Aufwecken beide Wake-Port-Variablen auf `false` setzen und `nosctl wake` oder `SIGUSR1` verwenden. Ein Wake-Befehl im Zustand `STARTING`, `RUNNING` oder `IDLE` meldet „server already active“ und wird nicht für einen späteren Neustart vorgemerkt.

## Automatischer Schlaf und Spielererkennung

| Variable | Standard | Bedeutung |
|---|---:|---|
| `AUTO_SLEEP_ENABLED` | `true` | Automatisches sauberes Beenden bei null Spielern aktivieren. |
| `IDLE_TIMEOUT_SECONDS` | `3600` | Erforderliche ununterbrochene Leerlaufzeit, mindestens 60 Sekunden. |
| `IDLE_CHECK_INTERVAL_SECONDS` | `30` | Intervall der Steam-A2S-Informationsabfragen. |
| `MIN_UPTIME_SECONDS` | `900` | Mindestlaufzeit, bevor automatisches Schlafen zulässig ist. |
| `IDLE_MIN_SUCCESSFUL_QUERIES` | `3` | Benötigte aufeinanderfolgende erfolgreiche A2S-Antworten mit null Spielern. |
| `A2S_TIMEOUT_SECONDS` | `2` | Timeout für die lokale A2S-Abfrage. Muss eine positive endliche Zahl sein. |
| `A2S_QUERY_HOST` | automatisch | Leer wählt `127.0.0.1` bei `MULTIHOME=0.0.0.0`, sonst die MultiHome-Adresse. |
| `ALLOW_LOG_ONLY_IDLE` | `false` | Logbasierte Join-/Leave-Erkennung zulassen, falls A2S nie funktioniert. Weniger sicher und standardmäßig deaktiviert. |

Das Standardverhalten ist bewusst konservativ: Ein A2S-Fehler setzt den Leerlauftimer zurück. Dadurch wird kein Server beendet, dessen Spielerzahl nicht bestätigt werden kann.

## Ports und Prozess

| Variable | Standard | Bedeutung |
|---|---:|---|
| `GAME_PORT` | `7777` | UDP-Spielport. |
| `QUERY_PORT` | `27015` | UDP-Steam-Query-Port und Quelle der A2S-Spielerzahl. |
| `MULTIHOME` | `0.0.0.0` | Adresse für `-MultiHome`. |
| `SERVER_READY_TIMEOUT_SECONDS` | `300` | Danach gilt ein lebender Prozess als laufend, auch wenn sich die bekannte Ready-Logzeile geändert hat. |
| `SERVER_STOP_TIMEOUT_SECONDS` | `90` | Schonfrist nach SIGINT, bevor eskaliert wird. |
| `EXTRA_SERVER_ARGS` | leer | Zusätzliche Argumente; werden mit Shell-ähnlicher Quotierung zerlegt, aber ohne Shell gestartet. |
| `USE_XVFB` | `true` in den mitgelieferten Beispielen | Wine-Befehle mit `xvfb-run -a` starten. Dies ist der empfohlene Deployment-Pfad und wird im Laufzeit-Smoke-Test geprüft. `false` erst verwenden, nachdem direkter Headless-Betrieb auf dem Zielhost getestet wurde. |

Beide Ports müssen als UDP veröffentlicht werden. Host- und Containerport sollten identisch bleiben, da `Engine.ini` und Kommandozeile dieselben Werte erhalten.

## Spielkonfiguration

Nur nicht leere Spielkonfigurationsvariablen überschreiben Werte in `Game.ini`. Leere Werte gelten als nicht gesetzt, sodass manuell gepflegte Werte erhalten bleiben. Die mitgelieferten Beispiele enthalten übliche Startwerte. Jede unten aufgeführte Variable kann zu `.env` oder zum `environment:`-Block in Portainer ergänzt werden, wenn sie durch den Container verwaltet werden soll. Unbekannte Abschnitte, Schlüssel und Kommentare bleiben erhalten.

| Variable | INI-Schlüssel | Zulässige Werte |
|---|---|---|
| `SERVER_NAME` | `ServerSetting.ServerName` | Text |
| `SAVE_NAME` | `ServerSetting.SaveName` | Text |
| `REQUIRE_PASSWORD` | `ServerSetting.NeedPassword` | Boolean |
| `SERVER_PASSWORD` / `_FILE` | `ServerSetting.Password` | Text/Secret-Datei |
| `ADMIN_PASSWORD` / `_FILE` | `ServerSetting.AdminPassword` | Text/Secret-Datei |
| `MAP` | `ServerSetting.OpenMap` | üblicherweise `Map01` oder `Map02` |
| `MAX_PLAYERS` | `ServerSetting.MaxPlayers` | 2–50 |
| `REGION` | `ServerSetting.Region` | z. B. `EU`, `NA`, `AS`, `AF`, `OC`, `SA`, `All` |
| `ZOMBIES_PER_PLAYER` | `ServerSetting.NumOfZombieSpawn` | 25–100 |
| `PVP` | `GameSettings.PVP` | Boolean |
| `ZOMBIE_ATTACK` | `GameSettings.ZombieAttack` | Boolean |
| `ZOMBIE_ATTACK_DAY` | `GameSettings.ZombieAttackDay` | 1–30 |
| `ATTACK_ZOMBIE_NUM` | `GameSettings.AttackZombieNum` | 1–5 |
| `ZOMBIE_NUM` | `GameSettings.ZombieNum` | 1–3 |
| `RUN_ZOMBIE_PERCENT` | `GameSettings.RunZombiePercent` | 0–1 |
| `ZOMBIE_STRENGTH` | `GameSettings.ZombieStreng` | 0–3 |
| `SPECIAL_ZOMBIE` | `GameSettings.SpecialZombie` | Boolean |
| `YEAR_DAYS` | `GameSettings.YearDay` | 1–365 |
| `DAY_LENGTH` | `GameSettings.DayLength` | 1–240 |
| `PERMADEATH` | `GameSettings.PermanentDead` | Boolean |
| `MATERIAL_AMOUNT` | `GameSettings.MaterialNum` | 0,1–10 |
| `ITEM_SPAWN` | `GameSettings.ItemSpawn` | 0,1–10 |
| `VIRUS_FATALITY_RATE` | `GameSettings.VirusFatalityRate` | 0–1 |
| `NOVICE_GIFT_BAG` | `GameSettings.GiftBagForNovices` | Boolean |
| `NPC_ITEM_SPAWN` | `GameSettings.NPCItemSpawn` | 0,1–10 |

Zukünftige oder seltene Einstellungen können über `GAME_INI_OVERRIDES` als JSON übergeben werden:

```env
GAME_INI_OVERRIDES={"ServerSetting":{"FutureSetting":"Value"},"GameSettings":{"AnotherValue":2}}
```

Für komplexes oder sensibles JSON steht `GAME_INI_OVERRIDES_FILE` zur Verfügung. Die referenzierte Datei muss in den Container eingebunden und für die konfigurierte `PUID` lesbar sein; die mitgelieferten Beispiele binden beliebige Override-Dateien nicht automatisch ein.

### Passwörter

Docker-Secrets werden empfohlen:

```bash
docker compose -f compose.yaml -f compose.secrets.yaml up -d
```

Leere direkte Passwortvariablen gelten als nicht gesetzt, damit optionale Compose-Interpolation sicher bleibt. Leere Passwortdateien werden abgelehnt. Beim erstmaligen Erstellen erfordert `REQUIRE_PASSWORD=true` ein nicht leeres `SERVER_PASSWORD` oder `SERVER_PASSWORD_FILE`. Wird kein Admin-Passwort vorgegeben, erzeugt der Container ein zufälliges Passwort und speichert es mit Modus `0600` unter `/data/state/generated-admin-password`.

## Wine und persistente Pfade

| Variable | Standard | Bedeutung |
|---|---:|---|
| `DATA_DIR` | `/data` | Wurzel der persistenten Daten. |
| `SERVER_DIR` | `/data/server` | SteamCMD-Installationsverzeichnis. |
| `SAVED_DIR` | `/data/saved` | Persistentes WRSH-`Saved`-Verzeichnis. |
| `STATE_DIR` | `/data/state` | Persistente Update-, Wine-Versions- und Secret-Marker. |
| `STEAMCMD_DIR` | `/data/steamcmd` | Beschreibbare SteamCMD-Installation. |
| `WINEPREFIX` | `/data/wine` | Persistenter 64-Bit-Wine-Prefix. |
| `RESET_WINEPREFIX` | `false` | Prefix bei diesem Start löschen und neu erzeugen. |
| `RESET_WINEPREFIX_ON_VERSION_CHANGE` | `true` | Prefix bei geänderter Ausgabe von `wine --version` neu erzeugen. Spielstände liegen getrennt und bleiben erhalten. |
| `WINEBOOT_TIMEOUT_SECONDS` | `600` | Maximale Dauer zum Erzeugen eines frischen Wine-Prefix. Danach wird die Prozessgruppe beendet und die Vorbereitung wechselt in den Retry-Backoff. |
| `WINEDEBUG` | `-all` | Wine-Debugeinstellung. |
| `PUID` / `PGID` | `1000` | Benutzer- und Gruppen-ID der Laufzeit. |
| `UMASK` | `0027` | Dateirechtemaske der Laufzeit; `Game.ini` wird zusätzlich auf `0600` gesetzt. |
| `FIX_PERMISSIONS` | `true` | Eigentümer einmal je UID/GID-Kombination rekursiv setzen; Marker liegt in `/data`. Akzeptiert dieselben Boolean-Schreibweisen wie die Python-Einstellungen. |

Die mitgelieferten Compose- und Portainer-Stacks binden das benannte Volume bewusst unter `/data` ein und stellen keine alternativen persistenten Wurzelpfade bereit. `DATA_DIR`, `SERVER_DIR`, `SAVED_DIR`, `STATE_DIR`, `STEAMCMD_DIR` und `WINEPREFIX` bleiben für benutzerdefinierte `docker run`- oder abgeleitete Image-Integrationen verfügbar. Jeder persistente Pfad muss absolut sein und unterhalb von `DATA_DIR` liegen.

## Steuerung und Healthcheck

| Variable | Standard | Bedeutung |
|---|---:|---|
| `RUNTIME_DIR` | `/run/nos` | Flüchtiges Laufzeitverzeichnis. Muss absolut sein. |
| `STATE_FILE` | `<RUNTIME_DIR>/state.json` | Optionale absolute Abweichung für die Statusdatei. Leer behält den abgeleiteten Standard. |
| `CONTROL_SOCKET` | `<RUNTIME_DIR>/control.sock` | Optionale absolute Abweichung für den Steuer-Socket. Leer behält den abgeleiteten Standard. Ein vorhandener Pfad, der kein Socket ist, wird niemals gelöscht. |
| `NOSCTL_TIMEOUT_SECONDS` | `5` | Maximale Verbindungs- und Lesezeit eines `nosctl`-Aufrufs. Muss eine positive endliche Zahl sein. |
| `HEALTHCHECK_MAX_HEARTBEAT_AGE` | `600` | Maximales Alter des Heartbeats in Sekunden, bevor der Container als ungesund gilt. |

```bash
docker exec no-one-survived nosctl status
docker exec no-one-survived nosctl wake
docker exec no-one-survived nosctl sleep
```

Der Healthcheck betrachtet `SLEEPING` als gesund. Er schlägt bei `ERROR`, einer fehlenden oder ungültigen Statusdatei, einer ungültigen Heartbeat-Konfiguration oder einem veralteten Heartbeat fehl. Fehler beim Start des Steuer-Sockets werden als Supervisor-Zustand `ERROR` protokolliert, statt vor der Aufräumlogik ungefangen abzubrechen.
