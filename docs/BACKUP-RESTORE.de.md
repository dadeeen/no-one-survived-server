# Sicherung und Wiederherstellung

[English](BACKUP-RESTORE.md) · [Zurück zur README](../README.de.md)

Nicht ersetzbar ist hauptsächlich `SAVED_DIR` (standardmäßig `/data/saved`). Serverdateien, SteamCMD und Wine-Prefix können neu erzeugt werden.

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

Das Backup-Hilfsprogramm legt Root-Rechte automatisch ab und sichert das konfigurierte `SAVED_DIR`. Backup-Archive und neu angelegte Backup-Verzeichnisse sind bereits bei der Erstellung privat (`0600` bzw. `0700`), auch bei Aufruf über `docker exec`. Standardziel ist `/data/backups`; fünf Archive werden aufbewahrt. `KEEP_BACKUPS` oder `BACKUP_DIR` können bei Bedarf über `docker exec --env` überschrieben werden. `KEEP_BACKUPS=0` deaktiviert die Aufbewahrungsbereinigung und behält alle Archive.

Eine Sicherung im selben Docker-Volume schützt vor fehlerhaften Updates, nicht vor Verlust des Hosts oder Volumes. Archive zusätzlich auf NAS oder ein anderes Backupsystem kopieren.

## Wiederherstellung

1. Den Container weiterlaufen lassen, den Gameserverprozess in den Zustand `SLEEPING` versetzen und dies mit `nosctl status` prüfen.
2. Wake-Verkehr vorübergehend verhindern und während des Restores kein manuelles Wake auslösen. Eine Firewallregel oder das vorübergehende Entfernen der veröffentlichten UDP-Ports reicht aus.
3. Das gewählte Archiv für den Container lesbar ablegen.
4. Ausführen:

   ```bash
   docker exec no-one-survived nos-restore /data/backups/saved-YYYY-MM-DD_HH-MM-SS.tar.gz
   ```

Das Restore-Hilfsprogramm verwendet einen privaten Staging-Baum (`umask 0077`), prüft zunächst das vollständige Archiv, lehnt Pfade außerhalb von `saved/`, Links und Spezialdateien ab und entpackt in ein temporäres Verzeichnis. Anschließend wird das bestehende `SAVED_DIR` in ein gleichgeordnetes `<name>.before-restore.<timestamp>.<pid>` umbenannt, der wiederhergestellte Ordner innerhalb desselben Volumes an seine Stelle verschoben und bei einem normalen Root-`docker exec` die konfigurierte Eigentümerschaft aus `PUID`/`PGID` angewendet.
