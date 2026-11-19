# Backup and restore

[Deutsch](BACKUP-RESTORE.de.md) · [Back to README](../README.md)

The irreplaceable data is `SAVED_DIR` (`/data/saved` by default). Server files, SteamCMD and the Wine prefix can be recreated.

## Consistent backup

Put the game server process to sleep first while leaving the container running:

```bash
docker exec no-one-survived nosctl status
docker exec no-one-survived nosctl sleep
```

Wait for `SLEEPING`, then run:

```bash
docker exec no-one-survived nos-backup
```

The backup helper drops root privileges automatically and backs up the configured `SAVED_DIR`. Backup archives and newly created backup directories are private from creation (`0600` and `0700`) even when invoked through `docker exec`. The default target is `/data/backups`, with five retained archives. Override `KEEP_BACKUPS` or `BACKUP_DIR` through `docker exec --env` when needed. `KEEP_BACKUPS=0` disables retention pruning and keeps all archives.

A backup inside the same Docker volume protects against bad updates but not against host/volume loss. Copy archives to NAS or another backup system.

## Restore

1. Keep the container running, put the game server process into `SLEEPING`, and verify the state with `nosctl status`.
2. Wake requests automatically wait for maintenance. If a helper reports `data is busy`, retry after the game or update has stopped.
3. Place the selected archive where the container can read it.
4. Run:

   ```bash
   docker exec no-one-survived nos-restore /data/backups/saved-YYYY-MM-DD_HH-MM-SS.ABC123.tar.gz
   ```

Both helpers drop root privileges and use the configured container identity. They hold an exclusive data lock throughout maintenance. A running game, update or other helper causes a `data is busy` failure without changing saves. `BACKUP_DIR` must be outside `SAVED_DIR`. Unique archive names preserve multiple backups within the same second.

Backups reject symbolic links and special files before creating an archive or pruning older backups. Hard-linked regular files are stored independently so the archive can be restored safely.

Before replacing any saves, `nos-restore` checks the entire archive and extracts it into a private directory (`umask 0077`). It rejects paths outside `saved/`, links and special files.

### Where are my previous saves after an interrupted restore?

During the swap, `nos-restore` renames the previous save directory. It sits alongside `SAVED_DIR` and, with the default settings, is named `/data/saved.before-restore.<timestamp>.<suffix>`. If the swap fails or is interrupted by `SIGHUP`, `SIGINT` or `SIGTERM`, the script tries to move the previous directory back to `SAVED_DIR`. If that fails, the error message gives the path to the retained data.

After `SIGKILL` or a host crash, automatic rollback may not have run. Before waking the server, check `SAVED_DIR` and look in its parent directory for the previous saves.
