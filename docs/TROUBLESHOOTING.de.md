# Fehlerbehebung

[English](TROUBLESHOOTING.md) · [Zurück zur README](../README.de.md)

## Container ist gesund, aber der Server nicht sichtbar

Ausführen:

```bash
docker exec no-one-survived nosctl status
```

`SLEEPING` gilt absichtlich als gesund. Query/Direktverbindung auslösen oder `nosctl wake` verwenden. Auf `RUNNING` beziehungsweise `IDLE` warten und dann die Clientverbindung erneut versuchen.

## Ein Paket weckt den Server nicht

Prüfen:

- UDP und nicht TCP ist veröffentlicht;
- `WAKE_ON_GAME_PORT` oder `WAKE_ON_QUERY_PORT` ist aktiviert;
- Quelladresse wird von `WAKE_SOURCE_POLICY` akzeptiert;
- bei `allowlist` enthält `WAKE_ALLOWED_NETWORKS` das beobachtete Quellnetz;
- `WAKE_PACKET_COUNT` ist nicht höher als die Zahl der Versuche;
- Firewall lässt das Paket zu;
- der Container und nicht nur der Gameserverprozess läuft.

Akzeptierte Pakete erscheinen im Log. Abgewiesene Pakete werden zur Vermeidung von Log-Fluten absichtlich nicht protokolliert.

## Server wacht direkt nach dem Einschlafen wieder auf

Erhöhen:

```env
WAKE_ARM_DELAY_SECONDS=15
WAKE_PACKET_COUNT=2
```

`WAKE_SOURCE_POLICY=private` beibehalten oder eine strikte `allowlist` verwenden. Wiederholte Steam-Favoritenabfragen oder Monitoring-Systeme können Query-Pakete erzeugen.

## Automatischer Schlaf tritt nie ein

In `nosctl status` prüfen:

- `players`;
- `a2s_ok`;
- `a2s_error`;
- `state` und `state_since`.

Die ausfallsichere Standardeinstellung schläft bei A2S-Fehlern nicht. Query-Port, Serverantwort und identische Host-/Containerportnummern kontrollieren. `ALLOW_LOG_ONLY_IDLE=true` ist möglich, kann bei geänderten Logformaten aber unsicher sein.

## SteamCMD-Update schlägt fehl

Die Erstinstallation benötigt Internetzugriff und ausreichend Speicherplatz. Vollständige SteamCMD-Ausgabe prüfen. Nur bei einer bereits vorhandenen Installation erlaubt `START_ON_UPDATE_FAILURE=true` den Start mit alten Dateien. Ein dauerhaft defektes Erstsetup darf damit nicht verdeckt werden.

Reparaturmodus:

```env
VALIDATE_ON_UPDATE=true
```

Nach erfolgreicher Validierung wieder auf `false` setzen.

## Wine-Prefix-Probleme nach Imageupdate

Einmalig setzen:

```env
RESET_WINEPREFIX=true
```

Container neu erzeugen und Variable anschließend entfernen. `/data/saved` liegt getrennt und wird nicht gelöscht.

## Berechtigungsfehler

Volume-Eigentümer und konfigurierte IDs prüfen:

```bash
docker exec no-one-survived id
docker exec no-one-survived ls -ld /data /data/saved
```

`PUID`/`PGID` ändern oder passenden `/data/.ownership-*`-Marker entfernen und Container neu erzeugen, damit der Eigentümer erneut gesetzt wird.

## Serverprozess stürzt wiederholt ab

Nach `MAX_CRASH_RESTARTS` wechselt der Supervisor in `ERROR`, der Healthcheck schlägt fehl. Einsammeln:

```bash
docker logs no-one-survived > nos-container.log
docker exec no-one-survived find /data/saved/Logs -maxdepth 1 -type f -printf '%f\n'
```

Spielupdates, Wine-Änderungen, ungültige `Game.ini`-Werte und freien Arbeitsspeicher prüfen. Das Neustartlimit nicht unbegrenzt erhöhen.

## Erstinstallation hat einen Saved-Ordner verschoben

Hat SteamCMD einen echten serverseitigen `Saved`-Ordner angelegt, obwohl `/data/saved` bereits Daten enthält, verschiebt der Supervisor den Konflikt nach:

```text
/data/state/orphaned-server-saved-<timestamp>
```

Dadurch werden keine Daten still überschrieben. Vor dem Löschen manuell vergleichen.
