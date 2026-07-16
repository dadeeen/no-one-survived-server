# Security policy

[Deutsch](SECURITY.de.md)

## Reporting a vulnerability

Use GitHub's private vulnerability reporting under **Security → Report a vulnerability**. Do not open a public issue containing vulnerability details.

If private reporting is unavailable, a public issue may be used only to request a private contact method. Do not include technical details, proof-of-concept material or sensitive data in that issue.

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
