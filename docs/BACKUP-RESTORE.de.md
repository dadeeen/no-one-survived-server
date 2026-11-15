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
2. Wake-Anforderungen warten automatisch auf laufende Wartung. Meldet das Hilfsprogramm `data is busy`, nach dem Ende des Spiels oder Updates erneut versuchen.
3. Das gewählte Archiv für den Container lesbar ablegen.
4. Ausführen:

   ```bash
   docker exec no-one-survived nos-restore /data/backups/saved-YYYY-MM-DD_HH-MM-SS.ABC123.tar.gz
   ```

Beide Hilfsprogramme legen Root-Rechte ab und verwenden die konfigurierte Containeridentität. Sie halten während der gesamten Wartung eine exklusive Datensperre. Ein laufendes Spiel, Update oder anderes Hilfsprogramm führt zum Abbruch mit `data is busy`; dabei werden keine Spielstände verändert. `BACKUP_DIR` muss außerhalb von `SAVED_DIR` liegen. Eindeutige Archivnamen erhalten auch mehrere Backups innerhalb derselben Sekunde.

Backups lehnen symbolische Links und Spezialdateien ab, bevor ein Archiv erstellt oder ein älteres Backup gelöscht wird. Reguläre Dateien mit Hardlinks werden unabhängig voneinander gespeichert, damit das Archiv sicher wiederhergestellt werden kann.

Das Restore-Hilfsprogramm verwendet einen privaten Staging-Baum (`umask 0077`), prüft das vollständige Archiv und lehnt Pfade außerhalb von `saved/`, Links und Spezialdateien ab. Anschließend wird das bestehende `SAVED_DIR` in ein gleichgeordnetes `<name>.before-restore.<timestamp>.<suffix>` umbenannt und durch den wiederhergestellten Ordner ersetzt. Bei einem fehlgeschlagenen Austausch oder Abbruch durch `SIGHUP`, `SIGINT` oder `SIGTERM` vor Abschluss des Austauschs versucht es, den bisherigen Ordner zurückzusetzen. Schlägt dies fehl, nennt die Fehlermeldung den Pfad der erhaltenen Daten. `SIGKILL` und ein Host-Absturz lassen sich nicht abfangen; in diesen Fällen vor dem Aufwecken des Servers nach dem erhaltenen Ordner suchen.
