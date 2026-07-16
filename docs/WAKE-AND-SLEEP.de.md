# Wake-on-Packet und automatischer Schlaf

[English](WAKE-AND-SLEEP.md) · [Zurück zur README](../README.de.md)

## Zustandsmodell

```text
PREPARING -> SLEEPING -> STARTING -> RUNNING -> IDLE -> STOPPING -> SLEEPING
                  ^          |          |          |
                  |          +-- Crash -+          +-- Timeout
                  +------------- UDP/manuelles Wake
```

Im Zustand `SLEEPING` bleibt der Container aktiv; nur Wine und der Gameserver sind beendet. Dadurch ist kein Zugriff auf den Docker-Socket nötig und derselbe Container kann die veröffentlichten UDP-Ports als Wake-Listener belegen.

## Übergabe der Ports

1. Der Listener bindet die ausgewählten UDP-Ports.
2. Leere Pakete und durch `WAKE_SOURCE_POLICY` abgewiesene Quellen werden ignoriert.
3. Pakete werden je Quell-IP innerhalb von `WAKE_PACKET_WINDOW_SECONDS` gezählt.
4. Nach `WAKE_PACKET_COUNT` schließt der Listener alle Sockets.
5. Der Supervisor startet Wine und `WRSHServer.exe`; diese binden anschließend dieselben Ports.

UDP besitzt keinen übertragbaren Verbindungszustand. Das Wake-Paket kann nicht an einen noch nicht laufenden Prozess weitergereicht werden. Der erste Join-/Query-Versuch läuft daher erwartungsgemäß in einen Timeout. Nach dem Start erneut versuchen.

## Wahl des Schwellenwerts

`WAKE_PACKET_COUNT=1` reagiert am schnellsten und ist hinter LAN-/VPN-Firewalls normalerweise passend. Bei nicht vertrauenswürdiger Erreichbarkeit und zufälligen Scans kann `2` oder `3` ungewollte Starts reduzieren.

Gezählt wird je Quell-IP, nicht global. Pakete verschiedener Quellen werden nicht kombiniert.

## Wake-Quellrichtlinie

Der empfohlene Standard ist bewusst einfach:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
```

`private` vertraut üblichen LAN-, Docker- und Overlay-IPv4-Bereichen und lehnt öffentliche IPv4-Quellen ab. Optionale Einträge in `WAKE_ALLOWED_NETWORKS` ergänzen diese eingebauten Bereiche.

Für eine strikte Liste:

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

Für bewusst öffentliches Wake steht `WAKE_SOURCE_POLICY=any` bereit; dann sollte gegebenenfalls `WAKE_PACKET_COUNT` erhöht werden. Die Wake-Richtlinie ist keine Firewall: Sie steuert nur, ob der schlafende Prozess startet.

Bewertet wird die Quelladresse, die der Container sieht. Bei normalem Docker-Port-Publishing bleibt die ursprüngliche LAN-Quelle für UDP üblicherweise erhalten. Die Wake-Logs prüfen; schreibt NAT oder ein Proxy die Adresse um, muss das übersetzte Netz erlaubt werden.

## Leerlaufentscheidung

Der Supervisor sendet A2S_INFO an den lokalen Steam-Query-Port. Der Leerlauftimer startet nur nach einer erfolgreichen Antwort mit null Spielern. Folgendes setzt ihn zurück:

- mindestens ein Spieler;
- A2S-Timeout oder ungültige Antwort;
- Beenden des Serverprozesses;
- manueller Stop.

Vor dem Schlafen müssen erfüllt sein:

- `MIN_UPTIME_SECONDS` ist abgelaufen;
- `IDLE_TIMEOUT_SECONDS` lang durchgehend null Spieler;
- mindestens `IDLE_MIN_SUCCESSFUL_QUERIES` erfolgreiche Null-Spieler-Antworten in Folge.

Diese ausfallsichere Strategie lässt den Server lieber weiterlaufen, als verbundene Spieler zu trennen.

## Manuelle Steuerung

```bash
docker exec no-one-survived nosctl wake
docker exec no-one-survived nosctl sleep
```

`nosctl sleep` ist ein administrativ erzwungener Schlafbefehl und blockiert nicht bei verbundenen Spielern. Vorher `nosctl status` prüfen.

## Zusammenspiel mit Updates

Empfehlung:

```env
UPDATE_ON_CONTAINER_START=true
UPDATE_ON_WAKE=false
UPDATE_INTERVAL_SECONDS=0
```

Damit wird der Server beim Containerstart aktualisiert und spätere Wake-Vorgänge bleiben schnell. Ein Updateintervall größer null führt SteamCMD im Schlafzustand aus. `UPDATE_ON_WAKE=true` verbessert die Versionssicherheit, kann aber jeden Wake deutlich verlängern.
