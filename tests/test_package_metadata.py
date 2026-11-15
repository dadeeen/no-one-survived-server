from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from nos_server import __version__


class PackageMetadataTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self) -> None:
        path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        project = tomllib.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(__version__, project["project"]["version"])


if __name__ == "__main__":
    unittest.main()
