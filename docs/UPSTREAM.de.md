# Hinweise zur Upstream-Kompatibilität

[English](UPSTREAM.md) · [Zurück zur README](../README.de.md)

Die spielspezifischen Kompatibilitätswerte stammen aus dem aktuellen CubeCoders-AMP-Template für No One Survived:

- Steam-App des Dedicated Servers: `2329680`;
- gegenüber Wine gesetzte Steam-App-ID des Spiels: `1963370`;
- Programmdatei: `WRSH/Binaries/Win64/WRSHServer.exe`;
- Positions-/Startargumente: `WRSH -server -stdout -FullStdOutLogOutput`;
- Spielport: UDP `7777`;
- Steam-Query-Port: UDP `27015`;
- Wine-Architektur: `win64`.

Die Containerlaufzeit selbst ist von CubeCoders unabhängig. Sie wird direkt gebaut aus:

- dem offiziellen Image `debian:trixie-slim`;
- offiziellen stabilen WineHQ-Paketen der gewählten Wine-11-Linie;
- Valves offiziellem SteamCMD-Bootstrap-Archiv.

Quellen:

- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survived.kvp>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedports.json>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedupdates.json>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedmetaconfig.json>
- <https://dl.winehq.org/wine-builds/debian/>
- <https://developer.valvesoftware.com/wiki/SteamCMD>

`WINE_MAJOR=11` wählt bei einem normalen Build das neueste verfügbare stabile Wine-11-Paket. Der Release-Workflow ermittelt einen unveränderlichen Debian-Image-Digest, zeichnet die exakte WineHQ-Paketversion und die SHA-256 des SteamCMD-Archivs aus einem Discovery-Image auf, baut mit diesen festgeschriebenen Hauptabhängigkeiten erneut und prüft den Kandidaten vor der Veröffentlichung per Smoke-Test.

Die tatsächlich verwendete Wine-Paketversion und der Hash des heruntergeladenen SteamCMD-Archivs liegen im Image unter `/usr/local/share/nos/wine-package-version` und `/usr/local/share/nos/steamcmd-bootstrap-sha256`.

Die Haupt-Pins machen das ausgewählte Debian-Image, Wine-Paket und SteamCMD-Archiv eindeutig. Debian-Repository-Metadaten und sämtliche transitiven APT-Pakete werden jedoch nicht über einen historischen Snapshot eingefroren. Deshalb wird keine bytegenaue Reproduzierbarkeit für einen beliebig weit in der Zukunft wiederholten Build zugesagt.

Vor jedem Release sollten die spielspezifischen Upstream-Dateien auf geänderte Programmpfade, Ports, Kommandozeilenargumente, Konfigurationsschlüssel, Ready-Muster oder Wine-Empfehlungen geprüft werden. Der Image-Smoke-Test muss außerdem SteamCMD-Start, amd64-/i386-Laufzeit und die Erstellung eines frischen Wine-Prefix bestätigen. Für produktives Vertrauen bleibt zusätzlich ein echter Gameserver-Integrationstest erforderlich; der PowerShell-Ablauf ist unter [Lokale CI](LOCAL-CI.de.md) beschrieben.
