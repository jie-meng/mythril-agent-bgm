#!/usr/bin/env python3
"""
Resume work music command for AI BGM.
"""

import click

from mythril_agent_bgm.commands.play import is_music_type_playing, start_background_player
from mythril_agent_bgm.utils.common import is_bgm_enabled


@click.command()
def resume():
    """Resume work music after a notification interruption.

    Switches back to looping work music only when notification music is
    still playing (e.g. after the user answers a permission prompt).
    Every other state -- work already playing, done playing or finished,
    or silence -- is left untouched, so hooking this on frequent events
    such as PostToolUse cannot resurrect work music after the turn ended.
    """
    if not is_bgm_enabled():
        return

    if not is_music_type_playing("notification"):
        return

    start_background_player("work", 0)
