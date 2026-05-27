#!/usr/bin/env python3
"""
Disable command for AI BGM.
"""

import click

from mythril_agent_bgm.utils.common import set_bgm_enable


@click.command()
def disable():
    """Turn the global AI BGM switch off.

    While off, ``bgm play`` becomes a no-op (AI tool hooks still fire but
    play no audio). This does NOT remove hooks from your AI tools — to do
    that, run ``bgm setup`` and uncheck the rows you want to unhook.
    """
    set_bgm_enable(False)
    click.echo("bgm: disabled")
