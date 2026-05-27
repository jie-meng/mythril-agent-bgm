#!/usr/bin/env python3
"""
Enable command for AI BGM.
"""

import click

from mythril_agent_bgm.utils.common import set_bgm_enable


@click.command()
def enable():
    """Turn the global AI BGM switch on.

    While on, ``bgm play`` plays music as usual. To hook/unhook BGM into a
    specific AI tool (Claude Code, Gemini, etc.), use ``bgm setup`` instead.
    """
    set_bgm_enable(True)
    click.echo("bgm: enabled")
