# Sicherheitsrichtlinie

[English](SECURITY.md)

## Sicherheitslücke melden

Nutze nach Möglichkeit die private Schwachstellenmeldung unter **Security → Report a vulnerability**. Ist diese Funktion nicht verfügbar, kontaktiere den Repository-Eigentümer auf einem privaten Weg. Lege für eine vermutete Sicherheitslücke kein öffentliches Issue an.

Nimm niemals Passwörter, Zugriffstoken, private Schlüssel, Spielstände oder ungeschwärzte private Netzwerkinformationen in einen Bericht auf.

## Unterstützte Versionen

Sicherheitskorrekturen richten sich an den aktuellen Standardbranch und das zuletzt veröffentlichte Image-Release. Vor dem ersten Image-Release wird nur der aktuelle Standardbranch unterstützt. Ältere Images und nicht unterstützte Kombinationen aus Wine- und Spielversion erhalten möglicherweise keine Korrekturen.

## Absicherung des Deployments

- Docker-Secrets oder `_FILE`-Variablen für Passwörter verwenden;
- `WAKE_SOURCE_POLICY=private` beibehalten oder eine strikte `allowlist` verwenden;
- den Docker-Socket nicht in den Container einbinden;
- den Container nicht im privilegierten Modus ausführen;
- bereitgestellte Images auf einen Release-Tag oder Image-Digest festschreiben.

## Betriebliche Vorsorge

Getestete Sicherungen von `/data/saved` außerhalb des Containerhosts aufbewahren.
