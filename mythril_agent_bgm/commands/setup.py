#!/usr/bin/env python3
"""
Setup AI tool integration command for AI BGM.
"""

import subprocess
import sys
from typing import List, Tuple

import click

from mythril_agent_bgm.commands.integrations import AIToolIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry
from mythril_agent_bgm.utils.colors import BOLD, GREEN, RED, YELLOW, color_text
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
                color_text(
                    "Error: curses module not available. Please install Python with curses support.",
                    RED,
                )
            )
            sys.exit(1)


_ensure_curses()

import curses  # noqa: E402


def check_tool_installed(integration: AIToolIntegration) -> bool:
    """Check if an AI tool is installed by verifying its config directory exists."""
    return integration.get_config_dir().exists()


def setup_integration(integration: AIToolIntegration) -> Tuple[bool, str]:
    """
    Setup a single integration.

    Delegates to integration.perform_setup(), which handles
    JSON-based and non-JSON (e.g. plugin file) integrations uniformly.

    Returns:
        Tuple of (success: bool, message: str)
    """
    return integration.perform_setup()


def curses_multi_select(
    stdscr: curses.window,
    title: str,
    items: List[str],
    preselected: List[bool] | None = None,
    disabled: set[int] | None = None,
    status_labels: List[str] | None = None,
    status_is_configured: set[int] | None = None,
) -> List[int] | None:
    """Interactive multi-select with arrow keys, space, and enter.

    Returns list of selected indices, or None if user cancelled (q/Esc).
    Disabled indices are shown dimmed and cannot be selected or toggled.

    Args:
        status_labels: Optional per-item status text appended after the name
            (e.g. ``"enabled"``, ``"not enabled"``, ``"not installed"``).
        status_is_configured: Indices whose status label should be rendered
            in green (already-configured visual cue).
    """
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_WHITE, -1)

    disabled = disabled or set()
    status_is_configured = status_is_configured or set()
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
            stdscr.addstr(row, 0, f"  {marker}  {all_item}", attr | curses.color_pair(1))
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
                row_attr = curses.A_DIM
                name_color = 0
            else:
                marker = "[x]" if selected[i] else "[ ]"
                row_attr = curses.A_REVERSE if cursor == i + 1 else 0
                name_color = curses.color_pair(2) if selected[i] else 0

            try:
                stdscr.addstr(row + i, 0, f"  {marker}  {item}", row_attr | name_color)
            except curses.error:
                pass

            if status_labels and i < len(status_labels) and status_labels[i]:
                label = f"  ({status_labels[i]})"
                if is_disabled:
                    label_color = curses.A_DIM
                elif i in status_is_configured:
                    label_color = curses.color_pair(2)
                else:
                    label_color = curses.color_pair(3)
                try:
                    stdscr.addstr(row + i, 4 + len(marker) + len(item), label, label_color)
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
                selected = [new_val if i not in disabled else False for i in range(len(items))]
            elif cursor - 1 not in disabled:
                selected[cursor - 1] = not selected[cursor - 1]
        elif key == ord("a"):
            enabled_sel = [s for i, s in enumerate(selected) if i not in disabled]
            new_val = not (bool(enabled_sel) and all(enabled_sel))
            selected = [new_val if i not in disabled else False for i in range(len(items))]
        elif key in (curses.KEY_ENTER, 10, 13):
            return [i for i, s in enumerate(selected) if s and i not in disabled]
        elif key in (ord("q"), 27):
            return None


def select_tools_interactive(integrations: List[AIToolIntegration]) -> List[int] | None:
    """Launch curses UI to select AI tools. Returns selected indices or None.

    Each tool is shown with one of three statuses:
    - ``not installed``: tool's config dir is missing; row is disabled.
    - ``enabled``:       BGM hooks/plugin are already installed; default unselected
                         (re-running setup is idempotent if the user opts in).
    - ``not enabled``:   tool is installed but BGM hooks are missing; default
                         selected as the most common intent.
    """
    items: List[str] = []
    status_labels: List[str] = []
    disabled: set[int] = set()
    configured: set[int] = set()
    preselected: List[bool] = []

    for i, integration in enumerate(integrations):
        _, tool_name = integration.get_tool_info()
        items.append(tool_name)

        if not check_tool_installed(integration):
            disabled.add(i)
            status_labels.append("not installed")
            preselected.append(False)
        elif integration.is_configured():
            configured.add(i)
            status_labels.append("enabled")
            preselected.append(False)
        else:
            status_labels.append("not enabled")
            preselected.append(True)

    return curses.wrapper(
        curses_multi_select,
        "Select AI tools to setup:",
        items,
        preselected=preselected,
        disabled=disabled,
        status_labels=status_labels,
        status_is_configured=configured,
    )


@click.command()
def setup():
    """Setup AI BGM integration with AI tools."""
    # Get all available integrations
    integrations = IntegrationRegistry.get_all_integrations()

    # Check which tools are installed
    installed_tools: List[AIToolIntegration] = []
    not_installed_tools: List[Tuple[AIToolIntegration, str]] = []

    for integration in integrations:
        if check_tool_installed(integration):
            installed_tools.append(integration)
        else:
            tool_id, tool_name = integration.get_tool_info()
            not_installed_tools.append((integration, tool_name))

    if not installed_tools:
        click.echo(color_text("\nNo installed AI tools detected", RED))
        click.echo("Please install and run one of the following tools first:")
        for _, tool_name in not_installed_tools:
            click.echo(f"  - {tool_name}")
        sys.exit(0)

    tool_indices = select_tools_interactive(integrations)
    if tool_indices is None or len(tool_indices) == 0:
        click.echo("No tools selected. Aborted.")
        sys.exit(0)

    click.echo(color_text(f"\nSelected {len(tool_indices)} tool(s), starting setup...", YELLOW))
    click.echo("-" * 50)

    success_count = 0
    fail_count = 0

    for idx in tool_indices:
        integration = integrations[idx]
        success, message = setup_integration(integration)
        if success:
            success_count += 1
            click.echo(color_text(message, GREEN))
        else:
            fail_count += 1
            click.echo(color_text(message, RED))

    click.echo("-" * 50)
    click.echo(color_text(f"Success: {success_count}, Failed: {fail_count}", BOLD))

    if not_installed_tools:
        click.echo()
        click.echo(color_text("Tools not detected (not installed):", YELLOW))
        for _, tool_name in not_installed_tools:
            click.echo(f"  - {tool_name}")

    click.echo()
    click.echo(color_text("[OK] AI BGM setup complete!", GREEN))
