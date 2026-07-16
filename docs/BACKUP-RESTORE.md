# Backup and restore

[Deutsch](BACKUP-RESTORE.de.md) · [Back to README](../README.md)

The irreplaceable data is `/data/saved`. Server files, SteamCMD and the Wine prefix can be recreated.

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

The backup helper drops root privileges automatically and writes archives with the configured runtime ownership. The default target is `/data/backups`, with five retained archives. Override `KEEP_BACKUPS` or `BACKUP_DIR` through `docker exec --env` when needed.

A backup inside the same Docker volume protects against bad updates but not against host/volume loss. Copy archives to NAS or another backup system.

## Restore

1. Keep the container running, put the game server process into `SLEEPING`, and verify the state with `nosctl status`.
2. Temporarily prevent wake traffic and do not issue a manual wake during the restore. A firewall rule or temporarily removing the published UDP ports is sufficient.
3. Place the selected archive where the container can read it.
4. Run:

   ```bash
   docker exec no-one-survived nos-restore /data/backups/saved-YYYY-MM-DD_HH-MM-SS.tar.gz
   ```

The restore helper validates the complete archive before changing live data, rejects paths outside `saved/`, links and special files, and extracts into a staging directory. It then renames the existing `/data/saved` directory to `saved.before-restore.<timestamp>.<pid>`, moves the restored directory into place on the same volume, and applies the configured `PUID`/`PGID` when invoked through the normal root-level `docker exec` command.
