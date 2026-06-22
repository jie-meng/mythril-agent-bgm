#!/usr/bin/env python3
"""
Select configuration command for AI BGM.
"""

import json
import subprocess
import sys
from typing import List, Optional

import click

from mythril_agent_bgm.utils.common import get_selection_file, load_builtin_config
from mythril_agent_bgm.utils.platform_utils import is_windows


def _ensure_curses() -> None:
    """Import curses, auto-installing windows-curses on Windows if needed."""
    try:
        import curses as _  # noqa: F401
    except ImportError:
        if is_windows():
            click.echo("Installing windows-curses ...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "windows-curses"],
                stdout=subprocess.DEVNULL,
            )
        else:
            click.echo(
                "Error: curses module not available. Please install Python with curses support.",
                err=True,
            )
            sys.exit(1)


_ensure_curses()

import curses  # noqa: E402


def load_current_selection() -> Optional[str]:
    """Load the current selection from user config directory."""
    config_path = get_selection_file()
    if not config_path.exists():
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("selected")


def save_selection(selection: str) -> None:
    """Save the selected BGM configuration to user config directory."""
    config_path = get_selection_file()

    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    data["selected"] = selection

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def curses_single_select(
    stdscr: curses.window,
    title: str,
    items: List[str],
    current_index: int = 0,
) -> Optional[int]:
    """Interactive single-select with arrow keys and enter/space.

    Returns the selected index, or None if the user cancelled (q/Esc).
    The cursor starts at current_index (the already-saved selection).
    """
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)

    cursor = current_index
    scroll_offset = 0

    def draw() -> None:
        nonlocal scroll_offset
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        stdscr.addstr(0, 0, title, curses.A_BOLD)
        hint = "↑/↓ or i/j move | Enter/Space confirm | q quit"
        stdscr.addstr(1, 0, hint, curses.color_pair(3))

        list_start_row = 3
        visible_rows = max_y - list_start_row - 2

        if cursor < scroll_offset:
            scroll_offset = cursor
        elif cursor >= scroll_offset + visible_rows:
            scroll_offset = cursor - visible_rows + 1

        for idx in range(visible_rows):
            item_idx = idx + scroll_offset
            if item_idx >= len(items):
                break
            item = items[item_idx]
            is_cursor = item_idx == cursor
            prefix = "▶ " if is_cursor else "  "
            attr = curses.A_REVERSE if is_cursor else 0
            color = curses.color_pair(2) if is_cursor else 0
            display = f"{prefix}{item}"
            try:
                stdscr.addstr(
                    list_start_row + idx, 0, display[: max_x - 1], attr | color
                )
            except curses.error:
                pass

        stdscr.refresh()

    while True:
        draw()
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("i"), ord("k")):
            cursor = (cursor - 1) % len(items)
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor = (cursor + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13, ord(" ")):
            return cursor
        elif key in (ord("q"), 27):
            return None


@click.command()
def select():
    """Interactively select BGM configuration."""
    config = load_builtin_config()
    options = list(config.keys())

    if not options:
        click.echo("Error: No available BGM configuration", err=True)
        sys.exit(1)

    current_selection = load_current_selection()
    current_index = (
        options.index(current_selection) if current_selection in options else 0
    )

    chosen_index = curses.wrapper(
        curses_single_select,
        "Select BGM configuration:",
        options,
        current_index=current_index,
    )

    if chosen_index is None:
        click.echo("Cancelled.")
        sys.exit(0)

    selection = options[chosen_index]
    save_selection(selection)
    click.echo(f"Selected: {selection}")
    click.echo(f"Config saved to: {get_selection_file()}")
