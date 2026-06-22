#!/usr/bin/env python3
"""
Toggle music command for AI BGM.
"""

import os
from pathlib import Path

import click

from mythril_agent_bgm.utils.common import get_pid_file
from mythril_agent_bgm.commands.stop import kill_existing_player
from mythril_agent_bgm.commands.play import start_background_player


def is_bgm_playing() -> bool:
    """
    Check if BGM is currently playing.

    Returns:
        True if BGM is playing, False otherwise.
    """
    pid_file = get_pid_file()

    if not pid_file.exists():
        return False

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # Check if the process is still running
        try:
            os.kill(pid, 0)  # This just checks if process exists
            return True
        except ProcessLookupError:
            # Process doesn't exist, remove stale PID file
            pid_file.unlink()
            return False
    except (ValueError, IOError):
        return False


@click.command()
def toggle():
    """Toggle music playback (play/stop).

    If music is playing, stop it. If not, start playing work music in loop.
    """
    if is_bgm_playing():
        # Stop the music
        killed = kill_existing_player()
        if killed:
            click.echo("Stopped BGM player")
        else:
            click.echo("No BGM player is currently running")
    else:
        # Start playing work music in infinite loop
        start_background_player("work", 0)
