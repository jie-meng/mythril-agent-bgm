#!/usr/bin/env python3
"""
Cleanup AI tool integration command for AI BGM.

Reverse of `bgm setup`: removes BGM hooks/plugins from AI tools.
"""

import subprocess
import sys
from typing import List, Tuple

import click

from aibgm.commands.integrations import AIToolIntegration
from aibgm.commands.integrations.registry import IntegrationRegistry
from aibgm.utils.colors import BOLD, GREEN, RED, YELLOW, color_text
from aibgm.utils.platform_utils import is_windows


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
                color_text(
                    "Error: curses module not available. Please install Python with curses support.",
                    RED,
                )
            )
            sys.exit(1)


_ensure_curses()

import curses  # noqa: E402


def _has_bgm_configured(integration: AIToolIntegration) -> bool:
    """Check if an integration currently has BGM hooks/plugins configured."""
    return integration.get_settings_path().exists()


def curses_multi_select(
    stdscr: curses.window,
    title: str,
    items: List[str],
    preselected: List[bool] | None = None,
    disabled: set[int] | None = None,
) -> List[int] | None:
    """Interactive multi-select with arrow keys, space, and enter.

    Returns list of selected indices, or None if user cancelled (q/Esc).
    Disabled indices are shown dimmed and cannot be selected or toggled.
    """
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_WHITE, -1)

    disabled = disabled or set()
    if preselected:
        selected = list(preselected)
    else:
        selected = [i not in disabled for i in range(len(items))]
    for i in disabled:
        selected[i] = False

    cursor = 0
    all_item = "Select All / Deselect All"
    total_items = 1 + len(items)
    enabled_count = len(items) - len(disabled)

    def _next_enabled(pos: int, direction: int) -> int:
        """Find next non-disabled position, wrapping around."""
        candidate = (pos + direction) % total_items
        attempts = 0
        while attempts < total_items:
            if candidate == 0 or candidate - 1 not in disabled:
                return candidate
            candidate = (candidate + direction) % total_items
            attempts += 1
        return 0

    def draw() -> None:
        stdscr.clear()
        stdscr.addstr(0, 0, title, curses.A_BOLD)
        hint = "Up/Down move | Space toggle | a all/none | Enter confirm | q quit"
        stdscr.addstr(1, 0, hint, curses.color_pair(3))

        row = 3
        enabled_sel = [s for i, s in enumerate(selected) if i not in disabled]
        all_selected = bool(enabled_sel) and all(enabled_sel)
        marker = "[x]" if all_selected else "[ ]"
        attr = curses.A_REVERSE if cursor == 0 else 0
        try:
            stdscr.addstr(
                row, 0, f"  {marker}  {all_item}", attr | curses.color_pair(1)
            )
        except curses.error:
            pass

        row += 1
        try:
            stdscr.addstr(row, 0, "  " + "-" * 36, curses.color_pair(1))
        except curses.error:
            pass

        row += 1
        for i, item in enumerate(items):
            is_disabled = i in disabled
            if is_disabled:
                marker = "[-]"
                attr = curses.A_DIM
                color = 0
            else:
                marker = "[x]" if selected[i] else "[ ]"
                attr = curses.A_REVERSE if cursor == i + 1 else 0
                color = curses.color_pair(2) if selected[i] else 0
            try:
                stdscr.addstr(row + i, 0, f"  {marker}  {item}", attr | color)
            except curses.error:
                pass

        count = sum(1 for i, s in enumerate(selected) if s and i not in disabled)
        try:
            stdscr.addstr(
                row + len(items) + 1,
                0,
                f"  {count}/{enabled_count} selected",
                curses.color_pair(3),
            )
        except curses.error:
            pass

        stdscr.refresh()

    while True:
        draw()
        key = stdscr.getch()

        if key == curses.KEY_UP or key == ord("k"):
            cursor = _next_enabled(cursor, -1)
        elif key == curses.KEY_DOWN or key == ord("j"):
            cursor = _next_enabled(cursor, 1)
        elif key == ord(" "):
            if cursor == 0:
                enabled_sel = [s for i, s in enumerate(selected) if i not in disabled]
                new_val = not (bool(enabled_sel) and all(enabled_sel))
                selected = [
                    new_val if i not in disabled else False for i in range(len(items))
                ]
            elif cursor - 1 not in disabled:
                selected[cursor - 1] = not selected[cursor - 1]
        elif key == ord("a"):
            enabled_sel = [s for i, s in enumerate(selected) if i not in disabled]
            new_val = not (bool(enabled_sel) and all(enabled_sel))
            selected = [
                new_val if i not in disabled else False for i in range(len(items))
            ]
        elif key in (curses.KEY_ENTER, 10, 13):
            return [i for i, s in enumerate(selected) if s and i not in disabled]
        elif key in (ord("q"), 27):
            return None


def select_tools_for_cleanup(
    integrations: List[AIToolIntegration],
) -> List[int] | None:
    """Launch curses UI to select AI tools to clean up. Returns selected indices or None."""
    no_config = {
        i
        for i, integration in enumerate(integrations)
        if not _has_bgm_configured(integration)
    }
    items = [
        f"{integration.get_tool_info()[1]}  (no BGM config found)"
        if i in no_config
        else integration.get_tool_info()[1]
        for i, integration in enumerate(integrations)
    ]
    preselected = [False for _ in range(len(items))]
    return curses.wrapper(
        curses_multi_select,
        "Select AI tools to clean up:",
        items,
        preselected=preselected,
        disabled=no_config,
    )


@click.command()
def cleanup():
    """Remove AI BGM hooks/plugins from AI tools (reverse of setup)."""
    integrations = IntegrationRegistry.get_all_integrations()

    configured: List[AIToolIntegration] = []
    not_configured: List[Tuple[AIToolIntegration, str]] = []

    for integration in integrations:
        if _has_bgm_configured(integration):
            configured.append(integration)
        else:
            _, tool_name = integration.get_tool_info()
            not_configured.append((integration, tool_name))

    if not configured:
        click.echo(color_text("\nNo AI tools with BGM configuration detected.", YELLOW))
        click.echo("Nothing to clean up.")
        sys.exit(0)

    tool_indices = select_tools_for_cleanup(integrations)
    if tool_indices is None or len(tool_indices) == 0:
        click.echo("No tools selected. Aborted.")
        sys.exit(0)

    click.echo(
        color_text(f"\nSelected {len(tool_indices)} tool(s), starting cleanup...", YELLOW)
    )
    click.echo("-" * 50)

    success_count = 0
    fail_count = 0

    for idx in tool_indices:
        integration = integrations[idx]
        success, message = integration.perform_cleanup()
        if success:
            success_count += 1
            click.echo(color_text(message, GREEN))
        else:
            fail_count += 1
            click.echo(color_text(message, RED))

    click.echo("-" * 50)
    click.echo(color_text(f"Success: {success_count}, Failed: {fail_count}", BOLD))
    click.echo()
    click.echo(color_text("[OK] AI BGM cleanup complete!", GREEN))
