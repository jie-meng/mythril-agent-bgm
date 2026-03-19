#!/usr/bin/env python3
"""Publish mythril-agent-bgm to PyPI.

Performs pre-flight checks, builds sdist + wheel, and uploads via twine.
Automatically ensures build & twine are installed.

Usage:
    python3 scripts/publish.py          # Publish to PyPI
    python3 scripts/publish.py --test   # Publish to TestPyPI first
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
INIT_FILE = PROJECT_ROOT / "aibgm" / "__init__.py"
DIST_DIR = PROJECT_ROOT / "dist"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    print(f"  {BOLD}${NC} {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)  # type: ignore[arg-type]


def _get_version_from_init() -> str:
    """Read __version__ from __init__.py."""
    content = INIT_FILE.read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        print(f"{RED}Error: __version__ not found in {INIT_FILE}{NC}")
        sys.exit(1)
    return match.group(1)


def _get_version_from_pyproject() -> str:
    """Read version from pyproject.toml."""
    content = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        print(f"{RED}Error: version not found in {PYPROJECT}{NC}")
        sys.exit(1)
    return match.group(1)


def _ensure_tools() -> None:
    """Ensure build and twine are installed."""
    for pkg in ("build", "twine"):
        try:
            __import__(pkg)
        except ImportError:
            print(f"  Installing {pkg}...")
            _run(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL,
                check=True,
            )


def _check_git_clean() -> bool:
    """Warn if there are uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.stdout.strip():
        print(f"{YELLOW}Warning: uncommitted changes detected.{NC}")
        try:
            answer = input(f"  Continue anyway? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        return answer in ("y", "yes")
    return True


def _clean_dist() -> None:
    """Remove old build artifacts."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print(f"  Cleaned {DIST_DIR}")


def _build() -> None:
    """Build sdist and wheel."""
    print(f"\n{BOLD}Building...{NC}")
    result = _run(
        [sys.executable, "-m", "build"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"{RED}Build failed.{NC}")
        sys.exit(1)


TESTPYPI_URL = "https://test.pypi.org/legacy/"

PYPI_ENV_VAR = "PYPI_API_TOKEN"
TESTPYPI_ENV_VAR = "TEST_PYPI_API_TOKEN"


def _has_pypirc_section(section: str) -> bool:
    """Check if ~/.pypirc has a given section."""
    pypirc = Path.home() / ".pypirc"
    if not pypirc.exists():
        return False
    return f"[{section}]" in pypirc.read_text()


def _resolve_credentials(test: bool) -> tuple[str | None, str | None]:
    """Resolve upload credentials: env var -> ~/.pypirc -> interactive prompt.

    Returns (username, password) or (None, None) if .pypirc handles it.
    """
    env_var = TESTPYPI_ENV_VAR if test else PYPI_ENV_VAR
    section = "testpypi" if test else "pypi"
    label = "TestPyPI" if test else "PyPI"

    token = os.environ.get(env_var)
    if token:
        print(f"  Using {env_var} from environment.")
        return "__token__", token

    if _has_pypirc_section(section):
        print(f"  Using [{section}] from ~/.pypirc.")
        return None, None

    print(f"  {YELLOW}No {label} credentials found.{NC}")
    print(f"  Options:")
    print(f"    1. Set {BOLD}{env_var}{NC} environment variable")
    print(f"    2. Add [{section}] section to ~/.pypirc")
    print(f"    3. Enter API token now")
    if test:
        print(
            f"  Get a token at: {BOLD}https://test.pypi.org/manage/account/token/{NC}"
        )
    else:
        print(f"  Get a token at: {BOLD}https://pypi.org/manage/account/token/{NC}")

    try:
        token = getpass.getpass(f"\n  Paste {label} API token (or Enter to abort): ")
    except (EOFError, KeyboardInterrupt):
        print()
        print(f"{RED}Aborted.{NC}")
        sys.exit(1)

    if not token.strip():
        print(f"{RED}No token provided. Aborted.{NC}")
        sys.exit(1)

    return "__token__", token.strip()


def _upload(test: bool = False) -> None:
    """Upload to PyPI or TestPyPI."""
    label = "TestPyPI" if test else "PyPI"
    print(f"\n{BOLD}Uploading to {label}...{NC}")

    username, password = _resolve_credentials(test)

    cmd = [sys.executable, "-m", "twine", "upload"]
    if test:
        if _has_pypirc_section("testpypi") and username is None:
            cmd += ["--repository", "testpypi"]
        else:
            cmd += ["--repository-url", TESTPYPI_URL]
    if username is not None:
        cmd += ["-u", username, "-p", password]  # type: ignore[list-item]
    cmd += [str(DIST_DIR / "*")]

    display_cmd = []
    for i, arg in enumerate(cmd):
        if i > 0 and cmd[i - 1] == "-p":
            display_cmd.append("***")
        else:
            display_cmd.append(arg)
    print(f"  {BOLD}${NC} {' '.join(display_cmd)}")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"{RED}Upload failed.{NC}")
        sys.exit(1)

    print(f"\n{GREEN}Published to {label} successfully.{NC}")


def main() -> None:
    test_mode = "--test" in sys.argv

    print(f"{BOLD}=== Publish mythril-agent-bgm ==={NC}\n")

    init_ver = _get_version_from_init()
    pyproject_ver = _get_version_from_pyproject()

    if init_ver != pyproject_ver:
        print(
            f"{RED}Version mismatch: "
            f"__init__.py={init_ver}, pyproject.toml={pyproject_ver}{NC}"
        )
        sys.exit(1)

    print(f"  Version: {GREEN}{init_ver}{NC}")

    if not _check_git_clean():
        print("Aborted.")
        sys.exit(1)

    _ensure_tools()
    _clean_dist()
    _build()

    if test_mode:
        _upload(test=True)
        print(
            f"\n  Test install: "
            f"{BOLD}pip install -i https://test.pypi.org/simple/ "
            f"mythril-agent-bgm=={init_ver}{NC}"
        )
        print(f"  Uninstall:    {BOLD}pip uninstall mythril-agent-bgm{NC}")
    else:
        _upload(test=False)
        print(f"\n  Install:   {BOLD}pip install mythril-agent-bgm=={init_ver}{NC}")
        print(f"  Uninstall: {BOLD}pip uninstall mythril-agent-bgm{NC}")


if __name__ == "__main__":
    main()
