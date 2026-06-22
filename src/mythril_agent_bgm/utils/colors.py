#!/usr/bin/env python3
"""
Terminal color utilities for AI BGM.

Provides ANSI escape code based color formatting for terminal output.
"""

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

# ANSI style codes
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"
RESET = "\033[0m"


def color_text(text: str, color: str) -> str:
    """
    Apply color to text using ANSI escape codes.

    Args:
        text: The text to colorize
        color: ANSI color code (e.g., GREEN, RED, BOLD)

    Returns:
        Colorized text with reset code appended

    Example:
        >>> color_text("Success", GREEN)
        '\033[92mSuccess\033[0m'
    """
    return f"{color}{text}{RESET}"


def success(text: str) -> str:
    """Format text as success message (green)."""
    return color_text(text, GREEN)


def error(text: str) -> str:
    """Format text as error message (red)."""
    return color_text(text, RED)


def warning(text: str) -> str:
    """Format text as warning message (yellow)."""
    return color_text(text, YELLOW)


def info(text: str) -> str:
    """Format text as info message (blue)."""
    return color_text(text, BLUE)


def bold(text: str) -> str:
    """Format text as bold."""
    return color_text(text, BOLD)
