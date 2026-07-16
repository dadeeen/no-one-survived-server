# Architektur

[English](ARCHITECTURE.md) · [Zurück zur README](../README.de.md)

Das Image ist ein kleiner Supervisor um eine unveränderte SteamCMD-Installation des Windows-Dedicated-Servers.

```text
tini
└── docker-entrypoint (Root-Setup, danach gosu)
    └── Python-Supervisor (unprivilegiert)
        ├── Unix-Steuersocket / nosctl
        ├── SteamCMD-Updater
        ├── Wine-Prefix-Verwaltung
        ├── erhaltender INI-Konfigurationsschreiber
        ├── UDP-Listener im Schlafzustand
        ├── A2S-Spielermonitor
        └── Wine -> WRSHServer.exe
```

Der Supervisor ruft Docker nie auf und bindet den Docker-Socket nicht ein. Ressourcen werden gespart, indem Wine und WRSH beendet werden, während der leichtgewichtige Supervisor aktiv bleibt.

## Invariante der Portbelegung

Jeder veröffentlichte UDP-Port gehört immer nur einer Komponente:

- im Schlafzustand dem `WakeListener`;
- während Start, Laufzeit und Idle dem `WRSHServer.exe` über Wine.

Der Listener schließt vor dem Start des Serverprozesses. Eine kurze Aktivierungsverzögerung verhindert, dass alte Pakete einen gerade beendeten Server sofort wieder aufwecken.

## Schutz vor Datenverlust

- Spielstände und Konfiguration liegen außerhalb des SteamCMD-Installationsverzeichnisses;
- `/data/server/WRSH/Saved` ist ein Symlink auf `/data/saved`;
- ein unerwarteter echter `Saved`-Ordner wird migriert oder beiseite verschoben, niemals still gelöscht;
- die Neuerzeugung des Wine-Prefix berührt keine Saves;
- Konfigurationsupdates erhalten unbekannte Schlüssel und Kommentare;
- Updatefehler verhindern standardmäßig den Start.

## Vertrauensgrenzen

Das Image führt aus:

- das ausgewählte offizielle Debian-Basisimage;
- offizielle WineHQ-Pakete;
- Valves SteamCMD-Bootstrap;
- anonym von SteamCMD geladene Gameserverdateien;
- den Python-/Shell-Supervisor dieses Repositorys.

Spielbinärdateien werden nicht in das veröffentlichte Image eingebaut. Der Release-Workflow zeichnet den Debian-Image-Digest, die exakte WineHQ-Paketversion und die SHA-256 des SteamCMD-Archivs des geprüften Kandidaten auf. Debian-Repository-Metadaten und transitive APT-Pakete werden nicht über einen historischen Paket-Snapshot eingefroren. Releases werden deshalb nicht als zu beliebigen zukünftigen Zeitpunkten bytegenau reproduzierbar bezeichnet.
