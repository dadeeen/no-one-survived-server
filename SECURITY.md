# Security policy

[Deutsch](SECURITY.de.md)

## Reporting a vulnerability

Use GitHub's private vulnerability reporting under **Security → Report a vulnerability** when it is available. Otherwise, contact the repository owner privately. Do not open a public issue for a suspected security vulnerability.

Never include passwords, access tokens, private keys, save files or unredacted private network information in a report.

## Supported versions

Security fixes target the current default branch and the most recent published image release. Before the first image release, only the current default branch is supported. Older images and unsupported Wine/game combinations may not receive fixes.

## Deployment hardening

- use Docker secrets or `_FILE` variables for passwords;
- keep `WAKE_SOURCE_POLICY=private` or use a strict `allowlist`;
- do not expose the Docker socket to the container;
- do not run the container in privileged mode;
- pin deployed images to a release tag or image digest.

## Operational resilience

Keep tested backups of `/data/saved` outside the container host.
