# Netzwerk und Wake-Sicherheit

[English](NETWORKING.md) · [Zurück zur README](../README.de.md)

Der Container ist netzwerkneutral. Er kann im LAN, über ein geroutetes VPN oder über öffentlich erreichbare UDP-Ports verwendet werden. Die Netzstruktur beeinflusst nur Routing, Firewallregeln und die Frage, welche Quellen einen schlafenden Server wecken dürfen.

## Erforderliche Ports

| Zweck | Protokoll | Standard |
|---|---|---:|
| Spielverkehr und Wake | UDP | 7777 |
| Steam-Query, Spielerzahl und Wake | UDP | 27015 |

Host- und Containerports sollten identisch veröffentlicht werden:

```yaml
ports:
  - "7777:7777/udp"
  - "27015:27015/udp"
```

Beide UDP-Ports müssen in Host-, LXC-/VM- und vorgeschalteten Firewalls für die Netze erlaubt sein, die sich verbinden sollen. Dieses Projekt benötigt keinen TCP-Port.

## Einfacher und sicherer Standard

Standardmäßig gilt:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
```

`private` akzeptiert Wake-Pakete aus diesen IPv4-Bereichen:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`
- `100.64.0.0/10` für Overlay-/CGNAT-artige Adressierung wie Tailscale
- `127.0.0.0/8` für lokale Tests

Damit funktionieren die meisten Heimnetze, Docker-Bridge-Netze, Site-to-Site-VPNs und Overlay-VPNs ohne individuelle CIDR-Konfiguration. Öffentliche IPv4-Quellen werden standardmäßig abgewiesen.

## Wake-Quellrichtlinien

| Richtlinie | Verhalten | Typischer Einsatz |
|---|---|---|
| `private` | Eingebaute private Bereiche plus optionale `WAKE_ALLOWED_NETWORKS` | Empfohlener Standard für LAN/VPN |
| `allowlist` | Nur ausdrücklich eingetragene CIDRs; eine leere Liste wird abgelehnt | Strenge Installationen oder ungewöhnliche Routing-Netze |
| `any` | Jede IPv4-Quelle, die den UDP-Port erreicht, darf wecken | Bewusst öffentlich erreichbare Server |

### Zusätzliches geroutetes Netz erlauben

Bei `private` ergänzt `WAKE_ALLOWED_NETWORKS` die eingebauten Bereiche:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=198.51.100.0/24
```

Der Dokumentationsbereich ist nur ein Beispiel. Einzutragen ist das Quellnetz, das der Container tatsächlich sieht.

### Strikte Allowlist

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

In diesem Modus werden Loopback- und private Netze nicht automatisch vertraut. Jedes erlaubte Quellnetz muss aufgeführt sein.

### Öffentliches Wake

```env
WAKE_SOURCE_POLICY=any
WAKE_PACKET_COUNT=2
```

Nur verwenden, wenn öffentliches Aufwecken beabsichtigt ist. Internet-Scanner, Monitoring und Steam-Abfragen können den Server sonst starten. Ein höherer `WAKE_PACKET_COUNT` reduziert versehentliches Wecken, ersetzt aber keine Zugriffskontrolle.

## LAN

Die Verbindung erfolgt über die LAN-Adresse des Docker-Hosts, der VM oder des LXC, zum Beispiel:

```text
192.168.10.50:7777
```

Die Standardrichtlinie `private` akzeptiert das Wake-Paket. Das erste Paket startet den Server nur; nach dem Wechsel zu `RUNNING` oder `IDLE` erneut verbinden:

```bash
docker exec no-one-survived nosctl status
```

## Geroutete VPNs: WireGuard, Tailscale und ähnliche

Ein geroutetes VPN kann dieselbe private Serveradresse erreichen. Voraussetzungen:

- Client- und Servernetze überschneiden sich nicht;
- Hin- und Rückroute zwischen Client- und Servernetz bestehen;
- Firewalls erlauben UDP 7777 und 27015;
- die vom Container gesehene Quelladresse ist durch die Wake-Richtlinie erlaubt.

Entfernte RFC1918-LANs und der Tailscale-Bereich `100.64.0.0/10` funktionieren mit dem Standard `private`. Ein abweichender nicht privater Tunnelbereich kann über `WAKE_ALLOWED_NETWORKS` ergänzt werden.

Direkt-IP oder Steam-Favorit verwenden. Layer-2-Broadcast-Erkennung wird durch ein geroutetes VPN normalerweise nicht weitergeleitet.

## Öffentliche IPv4-Erreichbarkeit

Für eine gewöhnliche öffentliche IPv4-Installation müssen Router/NAT und Firewalls beide UDP-Ports weiterleiten. Sollen beliebige Internet-Clients den Server wecken dürfen, muss dies ausdrücklich aktiviert werden:

```env
WAKE_SOURCE_POLICY=any
```

`allowlist` ist strenger, aber für Spieler mit wechselnden öffentlichen IP-Adressen oft unpraktisch.

## DS-Lite und CGNAT

DS-Lite und CGNAT verhindern normalerweise unaufgeforderte eingehende öffentliche IPv4-Portfreigaben. Nicht betroffen sind:

- Clients im selben LAN;
- Verkehr über einen bereits aufgebauten Site-to-Site-VPN-Tunnel;
- von innen aufgebaute Overlay-Netze wie Tailscale;
- ein VPN oder Relay auf einem öffentlich erreichbaren VPS.

Dieses Image stellt kein Relay bereit und umgeht DS-Lite nicht. Wake-Listener und Quellfilterung dieser Version arbeiten nur mit IPv4; natives öffentliches IPv6-Wake wird nicht zugesichert.

## Wake-Richtlinie ist keine Firewall

`WAKE_SOURCE_POLICY` entscheidet nur, ob ein Paket den schlafenden Gameserver starten darf. Sie entscheidet **nicht**, wer sich später mit dem laufenden Server verbinden darf.

Den tatsächlichen Zugriff steuern:

- Router- und Firewallregeln;
- Docker-Portbindungen;
- VPN-Routing und ACLs;
- das Serverpasswort.

Eine Quelle, die den Server nicht wecken darf, kann sich später trotzdem verbinden, wenn ein anderer Benutzer den Server gestartet hat und Netzwerk sowie Firewall den Zugriff erlauben.

## Gesehene Quelladresse prüfen

Nach einem Wake-Test die Logs kontrollieren:

```text
[wake] Accepted wake packet from 192.168.20.25:54321 -> UDP/27015
```

Falls NAT oder ein Proxy die Quelladresse umschreibt, muss das übersetzte Netz statt des ursprünglichen Clientnetzes erlaubt werden.

## Befehle zur Fehlersuche

```bash
ss -lunp | grep -E ':(7777|27015)\b'
docker port no-one-survived
docker logs --tail 200 no-one-survived
```

Erwarteter Portbesitz:

- `SLEEPING`: Der Python-Wake-Listener besitzt die gewählten Ports.
- `RUNNING` oder `IDLE`: Wine/WRSH besitzt die Ports.
