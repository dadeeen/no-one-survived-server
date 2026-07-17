[CmdletBinding()]
param(
    [switch]$NoCache,
    [switch]$Integration,
    [switch]$FullRuntime,
    [switch]$Audit,
    [switch]$KeepWorktree
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter()] [string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($ArgumentList -join ' ')"
    }
}

function Invoke-DockerScript {
    param(
        [Parameter(Mandatory)] [string]$Image,
        [Parameter(Mandatory)] [string]$Mount,
        [Parameter(Mandatory)] [string]$Script
    )

    Invoke-Native docker @(
        "run", "--rm",
        "--mount", $Mount,
        "--workdir", "/work",
        $Image,
        "sh", "-lc", ($Script -replace "`r", "")
    )
}

function Get-FreeUdpPort {
    $client = [System.Net.Sockets.UdpClient]::new(0)
    try {
        return ([System.Net.IPEndPoint]$client.Client.LocalEndPoint).Port
    }
    finally {
        $client.Dispose()
    }
}

function Get-ContainerStatus {
    param([Parameter(Mandatory)] [string]$ContainerName)

    $raw = & docker exec $ContainerName nosctl status 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        return $null
    }
    try {
        return (($raw -join "`n") | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Write-ContainerDiagnostics {
    param([Parameter(Mandatory)] [string]$ContainerName)

    Write-Host "`n== Container status =="
    $status = Get-ContainerStatus -ContainerName $ContainerName
    if ($null -ne $status) {
        Write-Host ($status | ConvertTo-Json -Depth 8)
    }
    else {
        Write-Host "Container status is unavailable."
    }

    Write-Host "`n== Container logs (last 300 lines) =="
    $logs = & docker logs --tail 300 $ContainerName 2>&1
    if ($LASTEXITCODE -eq 0 -and $logs) {
        foreach ($line in $logs) {
            Write-Host $line
        }
    }
    else {
        Write-Host "Container logs are unavailable."
    }
}

function Wait-ContainerState {
    param(
        [Parameter(Mandatory)] [string]$ContainerName,
        [Parameter(Mandatory)] [string[]]$AllowedStates,
        [Parameter(Mandatory)] [int]$TimeoutSeconds
    )

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastRetryAttempt = $null
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        $status = Get-ContainerStatus -ContainerName $ContainerName
        if ($null -ne $status) {
            if ($status.state -eq "ERROR") {
                $retryProperty = $status.PSObject.Properties["retry_in_seconds"]
                if ($null -ne $retryProperty) {
                    $attemptProperty = $status.PSObject.Properties["startup_retry_attempt"]
                    $attempt = if ($null -ne $attemptProperty) {
                        [string]$attemptProperty.Value
                    }
                    else {
                        "unknown"
                    }
                    if ($attempt -ne $lastRetryAttempt) {
                        Write-Host (
                            "Container reported a retryable ERROR " +
                            "(attempt $attempt, retry in $($retryProperty.Value)s); " +
                            "continuing to wait."
                        )
                        $lastRetryAttempt = $attempt
                    }
                }
                else {
                    Write-ContainerDiagnostics -ContainerName $ContainerName
                    throw "Container entered terminal ERROR state."
                }
            }
            elseif ($AllowedStates -contains [string]$status.state) {
                return $status
            }
        }
        Start-Sleep -Seconds 10
    }
    Write-ContainerDiagnostics -ContainerName $ContainerName
    throw "Timed out waiting for container state: $($AllowedStates -join ', ')"
}

function Assert-ContainerSymlinkTarget {
    param(
        [Parameter(Mandatory)] [string]$ContainerName,
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$ExpectedTarget
    )

    $targetOutput = & docker exec $ContainerName readlink -f $Path
    if ($LASTEXITCODE -ne 0 -or -not $targetOutput) {
        throw "Could not resolve container symlink target: $Path"
    }
    $target = ($targetOutput -join "`n").Trim()
    if ($target -ne $ExpectedTarget) {
        throw "Container symlink target mismatch: $Path -> $target (expected $ExpectedTarget)"
    }
}

$originalLocation = Get-Location
$repoRoot = $null
$worktree = $null
$integrationContainer = "nos-local-ci-integration-$PID"
$integrationVolume = "nos-local-ci-data-$PID"
$runIntegration = $Integration -or $FullRuntime

try {
    $repoRootOutput = & git rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or -not $repoRootOutput) {
        throw "Run this script from inside the repository."
    }
    $repoRoot = ($repoRootOutput -join "`n").Trim()

    Invoke-Native docker @("version")
    Invoke-Native docker @("buildx", "version")
    Invoke-Native docker @("compose", "version")

    $worktree = Join-Path $env:TEMP (
        "nos-local-ci-{0}-{1}" -f $PID, [guid]::NewGuid().ToString("N")
    )
    Invoke-Native git @(
        "-C", $repoRoot,
        "-c", "core.autocrlf=false",
        "worktree", "add", "--detach", $worktree, "HEAD"
    )
    Set-Location $worktree

    $commitOutput = & git rev-parse --short HEAD
    if ($LASTEXITCODE -ne 0 -or -not $commitOutput) {
        throw "Could not resolve the test commit."
    }
    $commit = ($commitOutput -join "`n").Trim()
    Write-Host "Testing commit $commit in isolated worktree $worktree"

    $mount = "type=bind,source=$worktree,target=/work"

    Write-Host "`n== Python 3.13: format, lint, typing, tests, compile =="
    Invoke-DockerScript -Image "python:3.13-slim" -Mount $mount -Script @'
set -eu
python -m pip install --disable-pip-version-check --root-user-action=ignore -r requirements-dev.txt
ruff format --check src tests
ruff check src tests
mypy --strict src/nos_server
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
'@

    if ($Audit) {
        Write-Host "`n== Optional Python development dependency audit =="
        Invoke-DockerScript -Image "python:3.13-slim" -Mount $mount -Script @'
set -eu
python -m pip install --disable-pip-version-check --root-user-action=ignore pip-audit
pip-audit -r requirements-dev.txt
'@
    }

    Write-Host "`n== Linux shell syntax and behavior =="
    Invoke-DockerScript -Image "debian:trixie-slim" -Mount $mount -Script @'
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends bash coreutils findutils grep gzip mawk python3 tar util-linux
cp -a /work /tmp/repo
chmod +x /tmp/repo/docker-entrypoint.sh /tmp/repo/scripts/*.sh
chown -R nobody:nogroup /tmp/repo
cd /tmp/repo
bash -n docker-entrypoint.sh scripts/*.sh
runuser -u nobody -- ./scripts/test-shell-behavior.sh
'@

    Write-Host "`n== Compose and Portainer models =="
    Copy-Item .env.example .env -Force
    New-Item -ItemType Directory -Path secrets -Force | Out-Null
    Set-Content -Path secrets/server_password.txt -Value "ci-server-test-value" -NoNewline
    Set-Content -Path secrets/admin_password.txt -Value "ci-admin-test-value" -NoNewline

    Invoke-Native docker @(
        "compose", "-f", "compose.yaml", "-f", "compose.build.yaml", "config"
    ) | Out-Null
    Invoke-Native docker @(
        "compose", "-f", "compose.yaml", "-f", "compose.secrets.yaml", "config"
    ) | Out-Null
    Invoke-Native docker @(
        "compose", "-f", "compose.yaml", "-f", "compose.build.yaml",
        "-f", "compose.secrets.yaml", "config"
    ) | Out-Null
    Invoke-Native docker @(
        "compose", "--env-file", "examples/portainer-stack.env.example",
        "-f", "examples/portainer-stack.yaml", "config"
    ) | Out-Null
    Invoke-Native docker @(
        "compose", "--env-file", "examples/portainer-stack.full.env.example",
        "-f", "examples/portainer-stack.full.yaml", "config"
    ) | Out-Null
    Copy-Item .env.full.example .env -Force
    Invoke-Native docker @(
        "compose", "-f", "compose.yaml", "-f", "compose.build.yaml",
        "-f", "compose.secrets.yaml", "config"
    ) | Out-Null

    Write-Host "`n== linux/amd64 image build =="
    $buildArguments = @(
        "buildx", "build",
        "--pull",
        "--platform", "linux/amd64",
        "--load",
        "--progress", "plain",
        "--build-arg", "VERSION=local-ci-$commit",
        "--tag", "no-one-survived-server:ci"
    )
    if ($NoCache) {
        $buildArguments += "--no-cache"
    }
    $buildArguments += "."
    Invoke-Native docker $buildArguments

    Write-Host "`n== Wine and SteamCMD runtime smoke test =="
    Invoke-Native docker @(
        "run", "--rm", "--platform", "linux/amd64",
        "--entrypoint", "/usr/local/bin/nos-image-smoke",
        "no-one-survived-server:ci"
    )

    $wineVersion = (& docker run --rm --entrypoint cat no-one-survived-server:ci /usr/local/share/nos/wine-package-version).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read the Wine package version."
    }
    $steamHash = (& docker run --rm --entrypoint cat no-one-survived-server:ci /usr/local/share/nos/steamcmd-bootstrap-sha256).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read the SteamCMD hash."
    }
    $imageSize = (& docker image inspect no-one-survived-server:ci --format "{{.Size}}").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the image."
    }
    Write-Host "Wine package: $wineVersion"
    Write-Host "SteamCMD SHA-256: $steamHash"
    Write-Host "Image size in bytes: $imageSize"

    if ($runIntegration) {
        Write-Host "`n== Real server integration test =="
        Invoke-Native docker @(
            "tag", "no-one-survived-server:ci", "nos-integration:local"
        )
        Invoke-Native docker @("volume", "create", $integrationVolume)
        $gamePort = Get-FreeUdpPort
        do {
            $queryPort = Get-FreeUdpPort
        } while ($queryPort -eq $gamePort)

        Invoke-Native docker @(
            "run", "-d",
            "--name", $integrationContainer,
            "-p", "${gamePort}:7777/udp",
            "-p", "${queryPort}:27015/udp",
            "-e", "PUID=1000",
            "-e", "PGID=1000",
            "-e", "USE_XVFB=true",
            "-e", "UPDATE_ON_CONTAINER_START=true",
            "-e", "PREPARE_ON_CONTAINER_START=true",
            "-e", "UPDATE_RETRY_DELAY_SECONDS=30",
            "-e", "START_SERVER_ON_CONTAINER_START=false",
            "-e", "AUTO_SLEEP_ENABLED=true",
            "-e", "IDLE_TIMEOUT_SECONDS=300",
            "-e", "MIN_UPTIME_SECONDS=0",
            "-e", "WAKE_SOURCE_POLICY=private",
            "-e", "WAKE_ALLOWED_NETWORKS=",
            "-v", "${integrationVolume}:/data",
            "nos-integration:local"
        )

        Write-Host "Waiting for the installation and SLEEPING state."
        $null = Wait-ContainerState -ContainerName $integrationContainer -AllowedStates @("SLEEPING") -TimeoutSeconds 5400
        Invoke-Native docker @(
            "exec", $integrationContainer, "test", "-f",
            "/data/server/WRSH/Binaries/Win64/WRSHServer.exe"
        )
        Invoke-Native docker @(
            "exec", $integrationContainer, "test", "-f", "/data/wine/system.reg"
        )
        Invoke-Native docker @(
            "exec", $integrationContainer, "test", "-L", "/data/server/WRSH/Saved"
        )
        Assert-ContainerSymlinkTarget `
            -ContainerName $integrationContainer `
            -Path "/data/server/WRSH/Saved" `
            -ExpectedTarget "/data/saved"

        Write-Host "Sending a UDP wake packet to host port $queryPort."
        $udp = [System.Net.Sockets.UdpClient]::new()
        try {
            [byte[]]$packet = [byte[]](0xff, 0xff, 0xff, 0xff) +
                [Text.Encoding]::ASCII.GetBytes("TSource Engine Query`0")
            [void]$udp.Send($packet, $packet.Length, "127.0.0.1", $queryPort)
        }
        finally {
            $udp.Dispose()
        }

        $null = Wait-ContainerState -ContainerName $integrationContainer -AllowedStates @("STARTING", "RUNNING", "IDLE") -TimeoutSeconds 300

        if ($FullRuntime) {
            Write-Host "Waiting for a successful real A2S response."
            $deadline = [DateTimeOffset]::UtcNow.AddSeconds(1200)
            $a2sOk = $false
            while ([DateTimeOffset]::UtcNow -lt $deadline) {
                $status = Get-ContainerStatus -ContainerName $integrationContainer
                if ($null -ne $status -and $status.a2s_ok -eq $true) {
                    $a2sOk = $true
                    break
                }
                Start-Sleep -Seconds 10
            }
            if (-not $a2sOk) {
                Write-ContainerDiagnostics -ContainerName $integrationContainer
                throw "No successful A2S response was observed."
            }
        }

        Invoke-Native docker @("exec", $integrationContainer, "nosctl", "sleep")
        $null = Wait-ContainerState -ContainerName $integrationContainer -AllowedStates @("SLEEPING") -TimeoutSeconds 180
        Invoke-Native docker @(
            "exec", $integrationContainer, "test", "-d", "/data/saved"
        )
    }

    Write-Host "`nAll requested local CI checks passed."
}
finally {
    Set-Location $originalLocation
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker rm -f $integrationContainer 2>$null | Out-Null
        & docker volume rm -f $integrationVolume 2>$null | Out-Null
    }

    if (
        $null -ne $repoRoot -and
        $null -ne $worktree -and
        (Test-Path $worktree) -and
        -not $KeepWorktree
    ) {
        & git -C $repoRoot worktree remove $worktree --force 2>$null | Out-Null
    }
    elseif ($KeepWorktree -and $null -ne $worktree) {
        Write-Host "Worktree retained at $worktree"
    }
}
