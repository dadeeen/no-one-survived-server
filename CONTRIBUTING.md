# Contributing / Mitwirken

## English

Keep changes small, focused and testable. Commit the intended change before running the routine Linux-based CI suite from PowerShell:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

The script tests committed `HEAD` in an isolated worktree. Use `-NoCache` for release candidates. Changes affecting Wine, SteamCMD, wake/sleep, ports or process lifecycle should also be tested with `-FullRuntime` when the required download time and bandwidth are available. The complete procedure is documented in [Local CI](docs/LOCAL-CI.md).

Do not commit game files, saves, passwords, Steam credentials, temporary CI data or generated Wine prefixes. Changes to wake/sleep behavior, lifecycle handling or deployment defaults must include regression tests and update both English and German documentation.

## Deutsch

Änderungen klein, fokussiert und testbar halten. Die beabsichtigte Änderung vor der regulären Linux-basierten CI-Suite committen und diese anschließend aus PowerShell starten:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

Das Skript testet den committeten Stand `HEAD` in einem isolierten Worktree. Für Release-Kandidaten `-NoCache` verwenden. Änderungen an Wine, SteamCMD, Wake/Sleep, Ports oder Prozesslebenszyklus sollten zusätzlich mit `-FullRuntime` geprüft werden, sofern Downloadzeit und Datenvolumen verfügbar sind. Der vollständige Ablauf steht unter [Lokale CI](docs/LOCAL-CI.de.md).

Keine Spielbinärdateien, Spielstände, Passwörter, Steam-Zugangsdaten, temporären CI-Daten oder erzeugten Wine-Prefixe committen. Änderungen an Wake/Sleep, Lebenszyklus oder Deployment-Standards benötigen Regressionstests sowie aktualisierte englische und deutsche Dokumentation.
