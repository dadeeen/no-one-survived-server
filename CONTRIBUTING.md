# Contributing / Mitwirken

## English

Keep changes small and testable. I commit the intended change and run the routine Linux-based CI suite from PowerShell:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

The script tests committed `HEAD` in an isolated worktree. Before a release I use `-NoCache`; for changes affecting Wine, SteamCMD, wake/sleep, ports or process lifecycle I also use `-FullRuntime` when the required download time and bandwidth are available. The complete procedure is documented in [Local CI](docs/LOCAL-CI.md).

Do not commit game files, saves, passwords, Steam credentials, temporary CI data or generated Wine prefixes. Changes to wake/sleep behavior, lifecycle handling or deployment defaults must include regression tests and update both English and German documentation.

## Deutsch

Änderungen klein und testbar halten. Ich committe die beabsichtigte Änderung und führe anschließend die reguläre Linux-basierte CI-Suite aus PowerShell aus:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

Das Skript testet den committeten Stand `HEAD` in einem isolierten Worktree. Vor einem Release verwende ich `-NoCache`. Bei Änderungen an Wine, SteamCMD, Wake/Sleep, Ports oder Prozesslebenszyklus nutze ich zusätzlich `-FullRuntime`, sofern Downloadzeit und Datenvolumen verfügbar sind. Der vollständige Ablauf steht unter [Lokale CI](docs/LOCAL-CI.de.md).

Keine Spielbinärdateien, Spielstände, Passwörter, Steam-Zugangsdaten, temporären CI-Daten oder erzeugten Wine-Prefixe committen. Änderungen an Wake/Sleep, Lebenszyklus oder Deployment-Standards benötigen Regressionstests sowie aktualisierte englische und deutsche Dokumentation.
