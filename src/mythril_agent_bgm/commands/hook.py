#!/usr/bin/env python3
"""
Host hook entry points for AI BGM.
"""

import json
import sys

import click

from mythril_agent_bgm.commands.play import is_music_type_playing, start_background_player
from mythril_agent_bgm.utils.common import is_bgm_enabled


def _read_stdin_payload() -> dict:
    """Read the JSON object a hook host writes to stdin.

    A human running ``bgm hook stop`` in a terminal must not block until
    Ctrl-D, and hook hosts always feed the payload through a pipe.
    """
    if sys.stdin is None or sys.stdin.isatty():
        return {}

    try:
        raw = sys.stdin.read()
    except (OSError, AttributeError, UnicodeDecodeError):
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if isinstance(payload, dict):
        return payload
    return {}


def _has_background_tasks(payload: dict) -> bool:
    """Check whether the Stop payload reports in-flight background work.

    ``session_crons`` is deliberately ignored: a scheduled wake-up does not
    mean work is happening now, and honouring it would keep music on all night.
    """
    tasks = payload.get("background_tasks")
    return isinstance(tasks, list) and bool(tasks)


@click.group()
def hook():
    """Entry points for host application hooks (not for direct use)."""


@hook.command()
def stop():
    """Keep work music while background tasks run, otherwise play done."""
    if not is_bgm_enabled():
        return

    if _has_background_tasks(_read_stdin_payload()):
        start_background_player("work", 0)
    else:
        start_background_player("done", 1)


@hook.command()
def idle():
    """Replace work music with done once the session goes idle."""
    if not is_bgm_enabled():
        return

    if is_music_type_playing("work"):
        start_background_player("done", 1)
