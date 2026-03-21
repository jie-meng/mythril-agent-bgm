#!/usr/bin/env python3
"""Bump project version in all tracked version files.

Updates:
  - pyproject.toml (`[project].version`)
  - mythril_agent_bgm/__init__.py (`__version__`)

Usage:
    python3 scripts/bump-version.py 0.1.3
    python3 scripts/bump-version.py          # show current versions
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
INIT_FILE = PROJECT_ROOT / "mythril_agent_bgm" / "__init__.py"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read_current_versions() -> dict[str, str]:
    """Read current versions from tracked files."""
    versions: dict[str, str] = {}

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    pyproject_match = re.search(
        r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE
    )
    versions["pyproject.toml"] = (
        pyproject_match.group(1) if pyproject_match else "NOT FOUND"
    )

    init_text = INIT_FILE.read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    versions["mythril_agent_bgm/__init__.py"] = (
        init_match.group(1) if init_match else "NOT FOUND"
    )

    return versions


def _show_current() -> None:
    """Show current versions."""
    versions = _read_current_versions()
    print("Current versions:")
    for path, version in versions.items():
        print(f"  {path}: {version}")


def _update_pyproject(new_version: str) -> None:
    """Update version in pyproject.toml."""
    text = PYPROJECT.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        print("Error: version field not found in pyproject.toml")
        sys.exit(1)
    PYPROJECT.write_text(updated, encoding="utf-8")


def _update_init(new_version: str) -> None:
    """Update __version__ in package __init__.py."""
    text = INIT_FILE.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(__version__\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_version}"',
        text,
        count=1,
    )
    if count == 0:
        print("Error: __version__ field not found in mythril_agent_bgm/__init__.py")
        sys.exit(1)
    INIT_FILE.write_text(updated, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        _show_current()
        print("\nUsage: python3 scripts/bump-version.py <new-version>")
        print("Example: python3 scripts/bump-version.py 0.1.3")
        return

    new_version = sys.argv[1]
    if not VERSION_RE.match(new_version):
        print(f"Error: '{new_version}' is not a valid semver (x.y.z)")
        sys.exit(1)

    _show_current()
    print(f"\nNew version: {new_version}")

    try:
        answer = input("Proceed? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(1)

    if answer not in ("y", "yes"):
        print("Aborted.")
        sys.exit(1)

    _update_pyproject(new_version)
    print("Updated pyproject.toml")

    _update_init(new_version)
    print("Updated mythril_agent_bgm/__init__.py")

    print("\nVerification:")
    _show_current()

    versions = _read_current_versions()
    if any(version != new_version for version in versions.values()):
        print("\nError: version mismatch detected after bump")
        sys.exit(1)

    print("\nDone. Don't forget to commit and tag:")
    print(f"  git add -A && git commit -m 'Bump version to {new_version}'")
    print(f"  git tag v{new_version}")


if __name__ == "__main__":
    main()
