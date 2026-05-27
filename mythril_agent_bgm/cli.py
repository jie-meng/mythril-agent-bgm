#!/usr/bin/env python3
"""
AI BGM - AI CLI Background Music Player
A unified CLI tool for playing background music during AI-assisted work sessions.
"""

import click

from mythril_agent_bgm.commands.play import play
from mythril_agent_bgm.commands.stop import stop
from mythril_agent_bgm.commands.select import select
from mythril_agent_bgm.commands.setup import setup
from mythril_agent_bgm.commands.toggle import toggle
from mythril_agent_bgm.commands.enable import enable
from mythril_agent_bgm.commands.disable import disable
from mythril_agent_bgm.utils.common import ensure_user_config_dir


class BGMGroup(click.Group):
    def invoke(self, ctx: click.Context) -> None:
        ensure_user_config_dir()
        super().invoke(ctx)


@click.group(cls=BGMGroup)
def cli():
    """AI CLI Background Music Player - Plays work music in loop and done music when finished."""
    pass


# Add subcommands
cli.add_command(play)
cli.add_command(stop)
cli.add_command(select)
cli.add_command(setup)
cli.add_command(toggle)
cli.add_command(enable)
cli.add_command(disable)


if __name__ == "__main__":
    cli()
