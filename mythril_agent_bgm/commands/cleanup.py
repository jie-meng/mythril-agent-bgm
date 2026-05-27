#!/usr/bin/env python3
"""
Cleanup AI tool integration command for AI BGM.

Reverse of `bgm setup`: removes BGM hooks/plugins from AI tools.
"""

import sys
from typing import List, Tuple

import click

from mythril_agent_bgm.commands.integrations import AIToolIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry
from mythril_agent_bgm.commands.setup import (
    check_tool_installed,
    curses_multi_select,
)
from mythril_agent_bgm.utils.colors import BOLD, GREEN, RED, YELLOW, color_text

import curses  # noqa: E402  (setup module ensures curses is importable)


def _has_bgm_configured(integration: AIToolIntegration) -> bool:
    """Check if an integration currently has BGM hooks/plugins configured."""
    return integration.is_configured()


def select_tools_for_cleanup(
    integrations: List[AIToolIntegration],
) -> List[int] | None:
    """Launch curses UI to select AI tools to clean up. Returns selected indices or None.

    Each tool is shown with one of three statuses:
    - ``not installed``: tool's config dir is missing; row is disabled.
    - ``enabled``:       BGM hooks/plugin are present; default selected for cleanup.
    - ``not enabled``:   tool is installed but no BGM hooks; row is disabled
                         (nothing to clean up).
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
        elif _has_bgm_configured(integration):
            configured.add(i)
            status_labels.append("enabled")
            preselected.append(True)
        else:
            disabled.add(i)
            status_labels.append("not enabled")
            preselected.append(False)

    return curses.wrapper(
        curses_multi_select,
        "Select AI tools to clean up:",
        items,
        preselected=preselected,
        disabled=disabled,
        status_labels=status_labels,
        status_is_configured=configured,
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

    click.echo(color_text(f"\nSelected {len(tool_indices)} tool(s), starting cleanup...", YELLOW))
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
