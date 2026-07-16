# Sicherung und Wiederherstellung

[English](BACKUP-RESTORE.md) · [Zurück zur README](../README.de.md)

Nicht ersetzbar ist hauptsächlich `/data/saved`. Serverdateien, SteamCMD und Wine-Prefix können neu erzeugt werden.

## Konsistente Sicherung

Den Gameserverprozess zunächst schlafen legen, den Container dabei aber weiterlaufen lassen:

```bash
docker exec no-one-survived nosctl status
docker exec no-one-survived nosctl sleep
```

Auf `SLEEPING` warten und dann ausführen:

```bash
docker exec no-one-survived nos-backup
```

Das Backup-Hilfsprogramm legt Root-Rechte automatisch ab und schreibt Archive mit der konfigurierten Laufzeit-Eigentümerschaft. Standardziel ist `/data/backups`; fünf Archive werden aufbewahrt. `KEEP_BACKUPS` oder `BACKUP_DIR` können bei Bedarf über `docker exec --env` überschrieben werden.

Eine Sicherung im selben Docker-Volume schützt vor fehlerhaften Updates, nicht vor Verlust des Hosts oder Volumes. Archive zusätzlich auf NAS oder ein anderes Backupsystem kopieren.

## Wiederherstellung

1. Den Container weiterlaufen lassen, den Gameserverprozess in den Zustand `SLEEPING` versetzen und dies mit `nosctl status` prüfen.
2. Wake-Verkehr vorübergehend verhindern und während des Restores kein manuelles Wake auslösen. Eine Firewallregel oder das vorübergehende Entfernen der veröffentlichten UDP-Ports reicht aus.
3. Das gewählte Archiv für den Container lesbar ablegen.
4. Ausführen:

   ```bash
   docker exec no-one-survived nos-restore /data/backups/saved-YYYY-MM-DD_HH-MM-SS.tar.gz
   ```

Das Restore-Hilfsprogramm prüft zunächst das vollständige Archiv, lehnt Pfade außerhalb von `saved/`, Links und Spezialdateien ab und entpackt in ein temporäres Verzeichnis. Anschließend wird der bestehende Ordner `/data/saved` in `saved.before-restore.<timestamp>.<pid>` umbenannt, der wiederhergestellte Ordner innerhalb desselben Volumes an seine Stelle verschoben und bei einem normalen Root-`docker exec` die konfigurierte Eigentümerschaft aus `PUID`/`PGID` angewendet.
