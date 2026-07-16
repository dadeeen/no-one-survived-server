# Lokale CI mit PowerShell

[English](LOCAL-CI.md) · [Zurück zur README](../README.de.md)

Wenn GitHub Actions nicht verfügbar oder das Kontingent ausgeschöpft ist, führe ich die Repository-Prüfungen mit dem mitgelieferten PowerShell-Skript lokal aus. Das Skript bildet die regulären CI-Prüfungen in Linux-Containern nach und kann zusätzlich den umfangreichen Integrationstest mit dem echten Gameserver durchführen.

## Voraussetzungen

Ich verwende:

- PowerShell 7 (`pwsh`);
- Git;
- Docker Desktop oder eine andere Docker Engine im Linux-Container-Modus;
- Docker Buildx und Docker Compose v2;
- ausreichend freien Speicherplatz und Datenvolumen für Debian, Wine, SteamCMD und den Download des Dedicated Servers.

Das Skript testet den aktuell festgeschriebenen Stand `HEAD` in einem isolierten Git-Worktree. Ich committe deshalb die zu prüfenden Änderungen vor dem Start. Nicht festgeschriebene Änderungen im Arbeitsverzeichnis werden bewusst nicht einbezogen.

## Reguläre lokale CI

Im Wurzelverzeichnis des Repositorys:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

Dabei werden ausgeführt:

- Ruff-Format- und Lint-Prüfungen mit Zielversion Python 3.13;
- strikte Mypy-Prüfung mit Zielversion Python 3.13;
- die vollständige Unit-Test-Suite unter Python 3.13;
- Python-Bytecode-Kompilierung;
- Linux-Shell-Syntax- und Verhaltenstests;
- alle unterstützten Compose- und Portainer-Kombinationen einschließlich Secrets-Overlay;
- ein frischer `linux/amd64`-Image-Build;
- der Laufzeit-Smoke-Test für Wine, Xvfb und SteamCMD;
- Ausgabe von Imagegröße und aufgezeichneten Upstream-Versionen.

Python 3.13 ist die einzige unterstützte Python-Linie, weil sie der Laufzeit im Debian-Trixie-Container entspricht. Python 3.14 wird für dieses containerspezifische Projekt bewusst weder zugesagt noch getestet.

Der temporäre Worktree wird automatisch entfernt. Das erzeugte Image bleibt lokal als `no-one-survived-server:ci` für weitere Prüfungen verfügbar.

## Sauberer releaseähnlicher Build

Vor einem Release umgehe ich zusätzlich den lokalen Docker-Layer-Cache:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache
```

Das dauert länger, deckt aber Annahmen auf, die durch einen früher bereits erfolgreichen Layer verdeckt werden könnten.

## Integration mit dem echten Dedicated Server

Der Integrationstest lädt mehrere Gigabyte herunter und kann ungefähr 110 Minuten dauern. Er installiert den aktuellen Dedicated Server, erzeugt den Wine-Prefix, wartet auf den Schlafzustand, sendet ein UDP-Wake-Paket, prüft den Start und fordert anschließend wieder einen sauberen Schlafzustand an:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache -Integration
```

Für die strengste Prüfung verlange ich zusätzlich eine erfolgreiche echte Steam-A2S-Antwort:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache -FullRuntime
```

`-FullRuntime` aktiviert den Integrationstest automatisch.

## Optionale Schalter

| Schalter | Bedeutung |
|---|---|
| `-NoCache` | Image ohne Wiederverwendung des Docker-Layer-Caches bauen. |
| `-Integration` | Echten Dedicated Server herunterladen und starten. |
| `-FullRuntime` | Integration ausführen und eine echte A2S-Antwort verlangen. |
| `-Audit` | Zusätzliche `pip-audit`-Prüfung für die festgeschriebenen Entwicklungswerkzeuge ausführen. |
| `-KeepWorktree` | Isolierten temporären Worktree zur Fehlersuche behalten. |

Die Anwendung besitzt keine externen Python-Laufzeitabhängigkeiten. Der optionale Audit betrifft deshalb Entwicklungswerkzeuge und nicht das ausgelieferte Wine-/SteamCMD-Image; er gehört nicht zum regulären lokalen Gate.

Ein fehlgeschlagener Befehl beendet den Lauf mit einem Fehlercode. Integrationscontainer und temporäres Docker-Volume werden im Aufräumpfad auch nach den meisten Fehlern entfernt.

## Release-Ablauf

Veröffentlichte Images werden nicht mehr bei jedem Push auf `main` erzeugt. Ich veröffentliche über einen gültigen Tag nach dem Muster `vMAJOR.MINOR.PATCH`, optional mit gültigem SemVer-Pre-Release-Zusatz, oder über einen bewusst ausgelösten manuellen Workflow. Vor dem Push eines Images führt der Release-Workflow Folgendes aus:

1. Release-Tag validieren und verhindern, dass ein Pre-Release `latest` verschiebt;
2. zuverlässig prüfen, dass der exakte Tag noch nicht existiert, und bei einer unklaren Registry-Antwort abbrechen;
3. unveränderlichen Debian-Image-Digest ermitteln;
4. ein Discovery-Image ohne Layer-Cache bauen;
5. exakte WineHQ-Paketversion und SHA-256 des SteamCMD-Archivs aufzeichnen;
6. einen zweiten Kandidaten ohne Cache mit den festgeschriebenen Hauptabhängigkeiten und den endgültigen Versionsmetadaten bauen;
7. den Laufzeit-Smoke-Test gegen genau diesen Kandidaten ausführen;
8. den lokalen BuildKit-Cache des Kandidaten exportieren und beim Publish ausschließlich diesen getesteten Cache wiederverwenden;
9. SBOM- und Provenienz-Informationen mit dem Image veröffentlichen.

Diese Festschreibungen machen die verwendeten Haupt-Upstreams eindeutig. Debian-Repository-Metadaten und transitive APT-Pakete werden jedoch nicht über einen historischen Paket-Snapshot eingefroren. Der Ablauf ist deshalb nicht als über beliebige zukünftige Zeitpunkte bytegenau reproduzierbar zu bezeichnen.
