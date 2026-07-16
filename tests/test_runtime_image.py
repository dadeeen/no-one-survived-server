from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeImageTests(unittest.TestCase):
    def test_runtime_is_built_from_official_debian_and_winehq(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("ARG DEBIAN_IMAGE=debian:trixie-slim", dockerfile)
        self.assertIn("FROM ${DEBIAN_IMAGE}", dockerfile)
        self.assertIn("ARG WINE_MAJOR=11", dockerfile)
        self.assertIn("dl.winehq.org/wine-builds", dockerfile)
        self.assertNotIn("cubecoders", dockerfile.lower())
        self.assertNotIn("ampstart", dockerfile.lower())

    def test_runtime_installs_trust_store_before_enabling_winehq(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        runtime = dockerfile.split("\nFROM ${DEBIAN_IMAGE}\n", 1)[1]
        winehq_copy = (
            "COPY --from=upstream-assets /assets/winehq.sources "
            "/etc/apt/sources.list.d/winehq.sources"
        )
        self.assertLess(runtime.index("ca-certificates;"), runtime.index(winehq_copy))
        self.assertIn("APT::Update::Error-Mode=any", runtime)

    def test_runtime_keeps_required_amd64_and_i386_support(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('test "${TARGETARCH}" = "amd64"', dockerfile)
        self.assertIn("dpkg --add-architecture i386", dockerfile)
        self.assertIn('"wine-${WINE_BRANCH}-i386=${resolved_wine_version}"', dockerfile)
        self.assertIn(
            '"wine-${WINE_BRANCH}-amd64=${resolved_wine_version}"', dockerfile
        )
        self.assertIn("libgcc-s1:i386", dockerfile)
        self.assertIn("libstdc++6:i386", dockerfile)
        self.assertIn("steamcmd-bootstrap-sha256", dockerfile)

    def test_runtime_smoke_test_is_packaged_and_run_by_ci(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        smoke_test = ROOT / "scripts/test-image-runtime.sh"
        self.assertTrue(smoke_test.is_file())
        self.assertIn(
            "COPY scripts/test-image-runtime.sh /usr/local/bin/nos-image-smoke",
            dockerfile,
        )
        self.assertIn("load: true", workflow)
        self.assertIn("/usr/local/bin/nos-image-smoke", workflow)

    def test_runtime_smoke_test_allows_the_nos_user_to_traverse_temp_root(self) -> None:
        smoke_test = (ROOT / "scripts/test-image-runtime.sh").read_text(
            encoding="utf-8"
        )
        ownership = 'chown nos:nos "$tmp"'
        first_nos_command = "gosu nos:nos"
        self.assertIn(ownership, smoke_test)
        self.assertLess(
            smoke_test.index(ownership), smoke_test.index(first_nos_command)
        )

    def test_runtime_smoke_test_terminates_wine_before_waiting(self) -> None:
        smoke_test = (ROOT / "scripts/test-image-runtime.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("== Wine prefix initialization ==", smoke_test)
        self.assertIn("timeout 240s xvfb-run -a /bin/sh -c", smoke_test)
        overrides = (
            'WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-'
            'mscoree,mshtml,winemenubuilder.exe=}"'
        )
        self.assertIn(overrides, smoke_test)
        wineboot_index = smoke_test.index("wineboot --init")
        kill_index = smoke_test.index("wineserver -k")
        wait_index = smoke_test.index("wineserver -w")
        self.assertLess(smoke_test.index(overrides), wineboot_index)
        self.assertLess(wineboot_index, kill_index)
        self.assertLess(kill_index, wait_index)
        self.assertIn('exit "$wineboot_status"', smoke_test)

    def test_local_ci_handles_retryable_errors_and_prints_terminal_diagnostics(
        self,
    ) -> None:
        local_runner = (ROOT / "scripts/run-local-ci.ps1").read_text(encoding="utf-8")
        self.assertIn("function Write-ContainerDiagnostics", local_runner)
        self.assertIn("Write-Host ($status | ConvertTo-Json -Depth 8)", local_runner)
        self.assertIn("docker logs --tail 300", local_runner)
        self.assertIn('PSObject.Properties["retry_in_seconds"]', local_runner)
        self.assertIn("continuing to wait.", local_runner)
        diagnostic_call = "Write-ContainerDiagnostics -ContainerName $ContainerName"
        error_throw = 'throw "Container entered terminal ERROR state."'
        self.assertLess(
            local_runner.index(diagnostic_call),
            local_runner.index(error_throw),
        )

    def test_local_build_defaults_match_the_runtime(self) -> None:
        compose = (ROOT / "compose.build.yaml").read_text(encoding="utf-8")
        self.assertIn("DEBIAN_IMAGE: ${DEBIAN_IMAGE:-debian:trixie-slim}", compose)
        self.assertIn("WINE_DIST: ${WINE_DIST:-trixie}", compose)
        self.assertIn("WINE_MAJOR: ${WINE_MAJOR:-11}", compose)
        self.assertIn("WINE_PACKAGE_VERSION: ${WINE_PACKAGE_VERSION:-}", compose)
        self.assertIn("STEAMCMD_SHA256: ${STEAMCMD_SHA256:-}", compose)
        self.assertNotIn("cubecoders", compose.lower())

    def test_python_support_matches_the_container_runtime(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        local_runner = (ROOT / "scripts/run-local-ci.ps1").read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('requires-python = ">=3.13,<3.14"', project)
        self.assertIn('target-version = "py313"', project)
        self.assertIn('python_version = "3.13"', project)
        self.assertIn('python-version: "3.13"', workflow)
        self.assertNotIn("3.14", workflow)
        self.assertIn('"python:3.13-slim"', local_runner)
        self.assertNotIn('"python:3.14-slim"', local_runner)
        self.assertNotIn('"python:3.11-slim"', local_runner)
        self.assertIn("[switch]$Audit", local_runner)
        self.assertNotIn("[switch]$SkipAudit", local_runner)
        self.assertIn("sys.version_info[:2] == (3, 13)", dockerfile)

    def test_release_workflow_is_tag_gated_and_pins_primary_inputs(self) -> None:
        workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        self.assertIn('tags: ["v*"]', workflow)
        self.assertNotIn("branches: [main]", workflow)
        self.assertIn("group: publish-${{ github.ref }}", workflow)
        self.assertIn("Validate release ref", workflow)
        self.assertIn("valid vMAJOR.MINOR.PATCH SemVer", workflow)
        self.assertIn("Numeric pre-release identifiers", workflow)
        self.assertIn("steps.release.outputs.publish_latest", workflow)
        self.assertIn("Refuse to overwrite an existing release tag", workflow)
        self.assertIn(
            "Unable to verify whether the release tag already exists", workflow
        )
        self.assertIn("DEBIAN_IMAGE=${{ steps.pins.outputs.debian_image }}", workflow)
        self.assertIn(
            "WINE_PACKAGE_VERSION=${{ steps.pins.outputs.wine_package_version }}",
            workflow,
        )
        self.assertIn(
            "STEAMCMD_SHA256=${{ steps.pins.outputs.steamcmd_sha256 }}", workflow
        )
        self.assertGreaterEqual(workflow.count("--no-cache"), 2)
        self.assertIn('cache-to "type=local', workflow)
        self.assertIn("cache-from: type=local", workflow)
        self.assertNotIn("cache-from: type=gha", workflow)
        self.assertLess(
            workflow.index("Resolve and smoke-test immutable upstream inputs"),
            workflow.index("Build and push pinned image"),
        )

    def test_ci_validates_secret_overlay_and_local_runner(self) -> None:
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        integration = (ROOT / "scripts/integration-test.sh").read_text(encoding="utf-8")
        local_runner = (ROOT / "scripts/run-local-ci.ps1").read_text(encoding="utf-8")
        self.assertIn("compose.secrets.yaml", workflow)
        self.assertIn("scripts/run-local-ci.ps1", workflow)
        self.assertNotIn("pip-audit", workflow)
        self.assertIn("if ($Audit)", local_runner)
        self.assertIn("-e USE_XVFB=true", integration)
        self.assertIn("while ($queryPort -eq $gamePort)", local_runner)
        self.assertTrue((ROOT / "scripts/run-local-ci.ps1").is_file())


if __name__ == "__main__":
    unittest.main()
