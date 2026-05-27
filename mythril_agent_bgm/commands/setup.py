#!/usr/bin/env python3
"""
Manage AI tool integrations for AI BGM.

``bgm setup`` is the single interactive screen for hooking BGM into AI
tools and un-hooking it. Confirming the screen applies the **diff**
between the current state and the user's selection:

- previously unhooked + now selected   → ``integration.perform_setup()``
- previously hooked   + now unselected → ``integration.perform_cleanup()``
- unchanged rows                       → skipped

This is unrelated to the global ``bgm enable / bgm disable`` toggle,
which controls whether ``bgm play`` does anything at runtime.
"""

import subprocess
import sys
from typing import List, Tuple

import click

from mythril_agent_bgm.commands.integrations import AIToolIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry
from mythril_agent_bgm.utils.colors import BOLD, GREEN, RED, YELLOW, color_text
from mythril_agent_bgm.utils.common import is_bgm_enabled
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
                    "Error: curses module not available. "
                    "Please install Python with curses support.",
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
    """Run setup for a single integration. See :class:`AIToolIntegration`."""
    return integration.perform_setup()


def curses_manage_integrations(
    stdscr: "curses.window",
    title: str,
    items: List[str],
    initial_state: List[bool],
    status_labels: List[str],
    disabled: set[int] | None = None,
    status_is_hooked: set[int] | None = None,
) -> List[bool] | None:
    """Interactive screen for managing per-tool BGM hook state.

    The selected checkboxes represent the **target** state. Use the returned
    list (paired with ``initial_state``) to compute which tools to hook
    (``False → True``) and which to unhook (``True → False``).

    Args:
        title: Screen title.
        items: Tool display names.
        initial_state: Current hook state per row (also the initial selection).
        status_labels: Right-side label per row (e.g. "hooked", "not hooked",
            "not installed").
        disabled: Row indices that cannot be toggled (e.g. uninstalled tools).
        status_is_hooked: Row indices currently hooked — used only for the
            green label color.

    Returns:
        Final per-row selection on Enter, or ``None`` on q/Esc.
    """
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)
    curses.init_pair(5, curses.COLOR_WHITE, -1)

    disabled = disabled or set()
    status_is_hooked = status_is_hooked or set()

    selected = [s and (i not in disabled) for i, s in enumerate(initial_state)]

    cursor = 0
    all_item = "Select All / Deselect All"
    total_items = 1 + len(items)
    toggleable_count = len(items) - len(disabled)

    def _next_enabled(pos: int, direction: int) -> int:
        candidate = (pos + direction) % total_items
        attempts = 0
        while attempts < total_items:
            if candidate == 0 or candidate - 1 not in disabled:
                return candidate
            candidate = (candidate + direction) % total_items
            attempts += 1
        return 0

    def _diff_counts() -> Tuple[int, int]:
        """Return (to_hook, to_unhook) — diff between selected and initial_state."""
        to_hook = sum(
            1
            for i in range(len(items))
            if i not in disabled and selected[i] and not initial_state[i]
        )
        to_unhook = sum(
            1
            for i in range(len(items))
            if i not in disabled and not selected[i] and initial_state[i]
        )
        return to_hook, to_unhook

    def draw() -> None:
        stdscr.clear()
        stdscr.addstr(0, 0, title, curses.A_BOLD)
        hint = "Up/Down move | Space toggle | a all/none | Enter apply | q cancel"
        stdscr.addstr(1, 0, hint, curses.color_pair(3))

        row = 3
        toggleable = [s for i, s in enumerate(selected) if i not in disabled]
        all_selected = bool(toggleable) and all(toggleable)
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
                elif i in status_is_hooked:
                    label_color = curses.color_pair(2)
                else:
                    label_color = curses.color_pair(3)
                try:
                    stdscr.addstr(row + i, 4 + len(marker) + len(item), label, label_color)
                except curses.error:
                    pass

        hooked_now = sum(1 for s in selected if s)
        to_hook, to_unhook = _diff_counts()
        if to_hook == 0 and to_unhook == 0:
            summary = f"  {hooked_now}/{toggleable_count} hooked  (no changes)"
            summary_color = curses.color_pair(3)
        else:
            parts = []
            if to_hook:
                parts.append(f"+{to_hook} hook")
            if to_unhook:
                parts.append(f"-{to_unhook} unhook")
            summary = f"  {hooked_now}/{toggleable_count} hooked  ({', '.join(parts)})"
            summary_color = curses.color_pair(2)
        try:
            stdscr.addstr(row + len(items) + 1, 0, summary, summary_color)
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
                toggleable = [s for i, s in enumerate(selected) if i not in disabled]
                new_val = not (bool(toggleable) and all(toggleable))
                selected = [new_val if i not in disabled else False for i in range(len(items))]
            elif cursor - 1 not in disabled:
                selected[cursor - 1] = not selected[cursor - 1]
        elif key == ord("a"):
            toggleable = [s for i, s in enumerate(selected) if i not in disabled]
            new_val = not (bool(toggleable) and all(toggleable))
            selected = [new_val if i not in disabled else False for i in range(len(items))]
        elif key in (curses.KEY_ENTER, 10, 13):
            return list(selected)
        elif key in (ord("q"), 27):
            return None


def _build_screen_inputs(
    integrations: List[AIToolIntegration],
) -> Tuple[List[str], List[bool], List[str], set[int], set[int]]:
    """Collect display data for :func:`curses_manage_integrations`.

    Returns:
        ``(items, initial_state, status_labels, disabled, hooked_indices)``.
    """
    items: List[str] = []
    initial_state: List[bool] = []
    status_labels: List[str] = []
    disabled: set[int] = set()
    hooked_indices: set[int] = set()

    for i, integration in enumerate(integrations):
        _, tool_name = integration.get_tool_info()
        items.append(tool_name)

        if not check_tool_installed(integration):
            disabled.add(i)
            initial_state.append(False)
            status_labels.append("not installed")
        elif integration.is_configured():
            hooked_indices.add(i)
            initial_state.append(True)
            status_labels.append("hooked")
        else:
            initial_state.append(False)
            status_labels.append("not hooked")

    return items, initial_state, status_labels, disabled, hooked_indices


def manage_integrations_interactive(
    integrations: List[AIToolIntegration],
) -> List[bool] | None:
    """Launch curses UI. Returns target state per tool, or ``None`` if cancelled."""
    items, initial_state, status_labels, disabled, hooked = _build_screen_inputs(integrations)
    return curses.wrapper(
        curses_manage_integrations,
        "Manage AI tool integrations:",
        items,
        initial_state=initial_state,
        status_labels=status_labels,
        disabled=disabled,
        status_is_hooked=hooked,
    )


@click.command()
def setup():
    """Manage AI BGM integrations (hook / unhook AI tools).

    Opens an interactive screen showing every supported AI tool's current
    hook state. Toggle rows with Space, press Enter to apply: newly checked
    rows are hooked, newly unchecked rows are unhooked.

    This only manages **per-tool** hook installation. To toggle the global
    BGM switch (so ``bgm play`` becomes a no-op), use ``bgm enable`` /
    ``bgm disable`` instead.
    """
    integrations = IntegrationRegistry.get_all_integrations()

    if not any(check_tool_installed(i) for i in integrations):
        click.echo(color_text("\nNo installed AI tools detected", RED))
        click.echo("Please install and run one of the following tools first:")
        for integration in integrations:
            _, tool_name = integration.get_tool_info()
            click.echo(f"  - {tool_name}")
        sys.exit(0)

    if not is_bgm_enabled():
        click.echo(
            color_text(
                "Note: AI BGM is globally disabled. Hooks will fire but produce no sound.\n"
                "      Run 'bgm enable' to turn it back on.",
                YELLOW,
            )
        )

    final_state = manage_integrations_interactive(integrations)
    if final_state is None:
        click.echo("Cancelled. No changes applied.")
        sys.exit(0)

    initial_state = [check_tool_installed(i) and i.is_configured() for i in integrations]

    to_hook: List[int] = []
    to_unhook: List[int] = []
    for idx, (was, now) in enumerate(zip(initial_state, final_state)):
        if not check_tool_installed(integrations[idx]):
            continue
        if not was and now:
            to_hook.append(idx)
        elif was and not now:
            to_unhook.append(idx)

    if not to_hook and not to_unhook:
        click.echo("No changes to apply.")
        sys.exit(0)

    click.echo(
        color_text(
            f"\nApplying changes: +{len(to_hook)} hook, -{len(to_unhook)} unhook ...",
            YELLOW,
        )
    )
    click.echo("-" * 50)

    success_count = 0
    fail_count = 0

    for idx in to_hook:
        success, message = integrations[idx].perform_setup()
        if success:
            success_count += 1
            click.echo(color_text(f"  hook   {message}", GREEN))
        else:
            fail_count += 1
            click.echo(color_text(f"  hook   {message}", RED))

    for idx in to_unhook:
        success, message = integrations[idx].perform_cleanup()
        if success:
            success_count += 1
            click.echo(color_text(f"  unhook {message}", GREEN))
        else:
            fail_count += 1
            click.echo(color_text(f"  unhook {message}", RED))

    click.echo("-" * 50)
    click.echo(color_text(f"Success: {success_count}, Failed: {fail_count}", BOLD))
    click.echo()
    click.echo(color_text("[OK] AI BGM integrations updated.", GREEN))
