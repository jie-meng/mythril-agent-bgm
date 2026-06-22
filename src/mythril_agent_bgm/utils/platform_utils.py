#!/usr/bin/env python3
"""
Platform detection utilities for cross-platform compatibility.
"""

import platform


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_unix() -> bool:
    """Check if running on Unix-like system (Linux, macOS, etc.)."""
    return not is_windows()


def get_platform_name() -> str:
    """Get the platform name (Windows, Darwin, Linux, etc.)."""
    return platform.system()
