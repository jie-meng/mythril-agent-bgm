#!/usr/bin/env python3
"""
AI BGM - AI CLI Background Music Player
A unified CLI tool for playing background music during AI-assisted work sessions.
"""

import click

from aibgm.commands.cleanup import cleanup
from aibgm.commands.play import play
from aibgm.commands.stop import stop
from aibgm.commands.select import select
from aibgm.commands.setup import setup
from aibgm.commands.toggle import toggle
from aibgm.commands.enable import enable
from aibgm.commands.disable import disable


@click.group()
def cli():
    """AI CLI Background Music Player - Plays work music in loop and done music when finished."""
    pass


# Add subcommands
cli.add_command(play)
cli.add_command(stop)
cli.add_command(select)
cli.add_command(setup)
cli.add_command(cleanup)
cli.add_command(toggle)
cli.add_command(enable)
cli.add_command(disable)


if __name__ == "__main__":
    cli()
