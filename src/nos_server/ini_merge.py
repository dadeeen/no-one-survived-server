from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from pathlib import Path

SECTION_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:[;#].*)?$")
KEY_RE = re.compile(r"^(\s*)([^=;#][^=]*?)(\s*)=(.*)$")


def _normal(value: str) -> str:
    return value.strip().casefold()


def merge_ini(
    path: Path, updates: Mapping[str, Mapping[str, str]], template: Path | None = None
) -> None:
    """Update selected INI keys while preserving unknown lines and comments."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if template and template.exists():
            shutil.copyfile(template, path)
        else:
            path.write_text("", encoding="utf-8")

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    if text and not text.endswith(("\n", "\r")):
        lines[-1] += "\n"

    pending = {
        _normal(section): {
            _normal(key): (key, str(value)) for key, value in values.items()
        }
        for section, values in updates.items()
    }
    section_names = {_normal(section): section for section in updates}
    current_section: str | None = None
    seen_sections: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    output: list[str] = []

    def append_missing(section_norm: str | None) -> None:
        if section_norm is None or section_norm not in pending:
            return
        for key_norm, (display_key, value) in pending[section_norm].items():
            marker = (section_norm, key_norm)
            if marker not in seen_keys:
                output.append(f"{display_key}={value}\n")
                seen_keys.add(marker)

    for line in lines:
        stripped = line.rstrip("\r\n")
        section_match = SECTION_RE.match(stripped)
        if section_match:
            append_missing(current_section)
            current_section = _normal(section_match.group(1))
            seen_sections.add(current_section)
            output.append(line)
            continue

        key_match = KEY_RE.match(stripped)
        if key_match and current_section in pending:
            key_norm = _normal(key_match.group(2))
            if key_norm in pending[current_section]:
                display_key, value = pending[current_section][key_norm]
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                output.append(f"{key_match.group(1)}{display_key}={value}{newline}")
                seen_keys.add((current_section, key_norm))
                continue
        output.append(line)

    append_missing(current_section)

    for section_norm, values in pending.items():
        if section_norm in seen_sections:
            continue
        if output and output[-1].strip():
            output.append("\n")
        output.append(f"[{section_names[section_norm]}]\n")
        for key_norm, (display_key, value) in values.items():
            output.append(f"{display_key}={value}\n")
            seen_keys.add((section_norm, key_norm))

    path.write_text("".join(output), encoding="utf-8")
