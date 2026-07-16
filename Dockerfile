# syntax=docker/dockerfile:1.7
ARG DEBIAN_IMAGE=debian:trixie-slim
ARG WINE_DIST=trixie
ARG STEAMCMD_URL=https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
ARG STEAMCMD_SHA256=""

FROM ${DEBIAN_IMAGE} AS upstream-assets
ARG WINE_DIST
ARG STEAMCMD_URL
ARG STEAMCMD_SHA256
ARG DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -o APT::Keep-Downloaded-Packages="false" -y --no-install-recommends \
        ca-certificates coreutils curl gnupg gzip tar; \
    install -d -m 0755 /assets /assets/steamcmd; \
    curl -fsSL --retry 5 --retry-all-errors \
        https://dl.winehq.org/wine-builds/winehq.key \
        -o /tmp/winehq.key; \
    gpg --batch --yes --dearmor \
        --output /assets/winehq-archive.key /tmp/winehq.key; \
    curl -fsSL --retry 5 --retry-all-errors \
        "https://dl.winehq.org/wine-builds/debian/dists/${WINE_DIST}/winehq-${WINE_DIST}.sources" \
        -o /assets/winehq.sources; \
    curl -fsSL --retry 5 --retry-all-errors \
        "${STEAMCMD_URL}" -o /tmp/steamcmd.tar.gz; \
    actual_steamcmd_sha256="$(sha256sum /tmp/steamcmd.tar.gz | awk '{print $1}')"; \
    if [ -n "${STEAMCMD_SHA256}" ]; then \
        test "${actual_steamcmd_sha256}" = "${STEAMCMD_SHA256}"; \
    fi; \
    printf '%s\n' "${actual_steamcmd_sha256}" >/assets/steamcmd-bootstrap-sha256; \
    tar -tzf /tmp/steamcmd.tar.gz | grep -Eq '(^|/)steamcmd[.]sh$'; \
    tar -xzf /tmp/steamcmd.tar.gz -C /assets/steamcmd; \
    chmod 0755 /assets/steamcmd/steamcmd.sh

FROM ${DEBIAN_IMAGE}
ARG DEBIAN_IMAGE
ARG DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH=amd64
ARG WINE_MAJOR=11
ARG WINE_DIST
ARG WINE_BRANCH=stable
ARG WINE_PACKAGE_VERSION=""
ARG VERSION=dev

LABEL org.opencontainers.image.title="No One Survived Dedicated Server" \
      org.opencontainers.image.description="Lean Debian/WineHQ runtime with SteamCMD, UDP wake and idle sleep" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/dadeeen/no-one-survived-server" \
      org.opencontainers.image.base.name="${DEBIAN_IMAGE}"

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN set -eux; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -o APT::Keep-Downloaded-Packages="false" -y --no-install-recommends \
        ca-certificates; \
    install -d -m 0755 /etc/apt/keyrings; \
    rm -rf /var/lib/apt/lists/*

COPY --from=upstream-assets /assets/winehq-archive.key /etc/apt/keyrings/winehq-archive.key
COPY --from=upstream-assets /assets/winehq.sources /etc/apt/sources.list.d/winehq.sources
COPY --from=upstream-assets /assets/steamcmd /opt/steamcmd-bootstrap
COPY --from=upstream-assets /assets/steamcmd-bootstrap-sha256 /usr/local/share/nos/steamcmd-bootstrap-sha256

RUN set -eux; \
    test "${TARGETARCH}" = "amd64"; \
    dpkg --add-architecture i386; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -o APT::Keep-Downloaded-Packages="false" -y --no-install-recommends \
        bash \
        cabextract \
        coreutils \
        findutils \
        gosu \
        gzip \
        mawk \
        passwd \
        python3 \
        tar \
        tini \
        tzdata \
        winbind \
        xauth \
        xvfb \
        libgcc-s1:i386 \
        libstdc++6:i386 \
        zlib1g:i386; \
    resolved_wine_version="${WINE_PACKAGE_VERSION}"; \
    if [ -z "${resolved_wine_version}" ]; then \
        resolved_wine_version="$( \
            apt-cache madison "wine-${WINE_BRANCH}-amd64" \
            | awk '{print $3}' \
            | grep -E "^${WINE_MAJOR}([.~+-]|$)" \
            | sort -V \
            | tail -n 1 \
        )"; \
    fi; \
    test -n "${resolved_wine_version}"; \
    apt-get install -o APT::Keep-Downloaded-Packages="false" -y --install-recommends \
        "wine-${WINE_BRANCH}-i386=${resolved_wine_version}" \
        "wine-${WINE_BRANCH}-amd64=${resolved_wine_version}" \
        "wine-${WINE_BRANCH}=${resolved_wine_version}" \
        "winehq-${WINE_BRANCH}=${resolved_wine_version}"; \
    install -d -m 0755 /opt/nos /usr/local/share/nos; \
    printf '%s\n' "${resolved_wine_version}" >/usr/local/share/nos/wine-package-version; \
    command -v wine wineboot wineserver xvfb-run gosu tini python3 >/dev/null; \
    python3 -c 'import sys; assert sys.version_info[:2] == (3, 13), sys.version'; \
    test -x /opt/steamcmd-bootstrap/linux32/steamcmd; \
    if ldd /opt/steamcmd-bootstrap/linux32/steamcmd | grep -q 'not found'; then \
        ldd /opt/steamcmd-bootstrap/linux32/steamcmd; \
        exit 1; \
    fi; \
    wine --version | grep -E "^wine-${WINE_MAJOR}([.]|$)"; \
    dpkg --print-foreign-architectures | grep -qx i386; \
    groupadd --system nos; \
    useradd --system --gid nos --home-dir /data/home --shell /bin/bash nos; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /opt/nos/pyproject.toml
COPY src /opt/nos/src
COPY config /opt/nos/config
COPY docker-entrypoint.sh /usr/local/bin/nos-entrypoint
COPY scripts/backup.sh /usr/local/bin/nos-backup
COPY scripts/restore.sh /usr/local/bin/nos-restore
COPY scripts/test-image-runtime.sh /usr/local/bin/nos-image-smoke

RUN chmod 0755 \
        /usr/local/bin/nos-entrypoint \
        /usr/local/bin/nos-backup \
        /usr/local/bin/nos-restore \
        /usr/local/bin/nos-image-smoke; \
    ln -s /opt/nos/src/nos_server/nosctl.py /usr/local/share/nosctl.py; \
    printf '#!/usr/bin/env bash\nexec python3 -m nos_server.nosctl "$@"\n' >/usr/local/bin/nosctl; \
    printf '#!/usr/bin/env bash\nexec python3 -m nos_server.healthcheck\n' >/usr/local/bin/nos-healthcheck; \
    chmod 0755 /usr/local/bin/nosctl /usr/local/bin/nos-healthcheck

ENV DATA_DIR=/data \
    RUNTIME_DIR=/run/nos \
    PYTHONPATH=/opt/nos/src \
    PYTHONUNBUFFERED=1 \
    WINEARCH=win64 \
    WINEDEBUG=-all

EXPOSE 7777/udp 27015/udp
VOLUME ["/data"]
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --start-period=10m --retries=5 CMD ["/usr/local/bin/nos-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/nos-entrypoint"]
CMD ["python3", "-m", "nos_server.supervisor"]
