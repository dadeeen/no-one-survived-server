# Upstream compatibility notes

[Deutsch](UPSTREAM.de.md) · [Back to README](../README.md)

The game-specific compatibility values are derived from the current CubeCoders AMP template for No One Survived:

- dedicated-server Steam app: `2329680`;
- game Steam app ID exposed to Wine: `1963370`;
- executable: `WRSH/Binaries/Win64/WRSHServer.exe`;
- positional/start arguments: `WRSH -server -stdout -FullStdOutLogOutput`;
- game port: UDP `7777`;
- Steam query port: UDP `27015`;
- Wine architecture: `win64`.

The container runtime itself is independent of CubeCoders. It is built directly from:

- the official `debian:trixie-slim` image;
- official WineHQ stable packages from the selected Wine 11 release line;
- Valve's official SteamCMD bootstrap archive.

Sources:

- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survived.kvp>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedports.json>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedupdates.json>
- <https://github.com/CubeCoders/AMPTemplates/blob/main/no-one-survivedmetaconfig.json>
- <https://dl.winehq.org/wine-builds/debian/>
- <https://developer.valvesoftware.com/wiki/SteamCMD>

`WINE_MAJOR=11` selects the newest available stable Wine 11 package during an ordinary build. The release workflow resolves an immutable Debian image digest, records the exact WineHQ package version and SteamCMD archive SHA-256 from a discovery image, rebuilds with those primary inputs pinned and smoke-tests the candidate before publication.

The resolved Wine package version and downloaded SteamCMD archive hash are stored inside the image at `/usr/local/share/nos/wine-package-version` and `/usr/local/share/nos/steamcmd-bootstrap-sha256`.

The primary pins make the selected Debian image, Wine package and SteamCMD archive explicit. They do not freeze Debian repository metadata or every transitive APT package through a historical snapshot, so releases are not claimed to be byte-for-byte reproducible when rebuilt at arbitrary future dates.

Before each release, compare the game-specific upstream files for changed executable paths, ports, command-line arguments, configuration keys, readiness patterns or Wine recommendations. The image smoke test must also confirm SteamCMD startup, amd64/i386 runtime support and creation of a fresh Wine prefix. A real game-server integration run remains required for production confidence; the PowerShell procedure is documented under [Local CI](LOCAL-CI.md).
