#!/usr/bin/env python3
"""
Host hook entry points for AI BGM.
"""

import json
import sys
from pathlib import Path

import click

from mythril_agent_bgm.commands.play import is_music_type_playing, start_background_player
from mythril_agent_bgm.commands.stop import kill_existing_player
from mythril_agent_bgm.utils.common import get_config_dir, get_lock_file, is_bgm_enabled
from mythril_agent_bgm.utils.process import FileLock


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


def _owner_file() -> Path:
    """File naming the host session that most recently started work music.

    Claude Code runs every session against one global player, so a session
    ending must not silence music another session is still using. The file is
    advisory: when it is missing, commands keep their previous behaviour.
    """
    return get_config_dir() / "bgm_work_owner"


def _session_id(payload: dict) -> str:
    session_id = payload.get("session_id")
    return session_id if isinstance(session_id, str) else ""


def _owner() -> str:
    try:
        return _owner_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _set_owner(session_id: str) -> None:
    if not session_id:
        return
    try:
        _owner_file().write_text(session_id, encoding="utf-8")
    except OSError:
        pass


def _clear_owner() -> None:
    try:
        _owner_file().unlink()
    except OSError:
        pass


def _belongs_elsewhere(session_id: str) -> bool:
    """Whether another session owns the music this payload's session sees."""
    owner = _owner()
    return bool(owner) and bool(session_id) and owner != session_id


@click.group()
def hook():
    """Entry points for host application hooks (not for direct use)."""


@hook.command()
def work():
    """Start work music for a new turn and claim its ownership."""
    if not is_bgm_enabled():
        return

    session_id = _session_id(_read_stdin_payload())
    _set_owner(session_id)
    if not is_music_type_playing("work"):
        start_background_player("work", 0)


@hook.command()
def stop():
    """Keep work music while background tasks run, otherwise play done."""
    if not is_bgm_enabled():
        return

    payload = _read_stdin_payload()
    session_id = _session_id(payload)

    if _has_background_tasks(payload):
        _set_owner(session_id)
        if not is_music_type_playing("work"):
            start_background_player("work", 0)
        return

    if _belongs_elsewhere(session_id):
        return

    start_background_player("done", 1)
    _clear_owner()


@hook.command()
def idle():
    """Replace this session's work music with done once it goes idle."""
    if not is_bgm_enabled():
        return

    session_id = _session_id(_read_stdin_payload())
    if _belongs_elsewhere(session_id):
        return

    if is_music_type_playing("work"):
        start_background_player("done", 1)


@hook.command()
def end():
    """Stop music only when the ending session is the one playing it."""
    session_id = _session_id(_read_stdin_payload())
    if not session_id:
        return

    # Re-read under the same lock start/stop use: a prompt from another
    # session may have claimed the music between our read and the kill.
    with FileLock(str(get_lock_file())):
        if _owner() != session_id:
            return
        kill_existing_player()
        _clear_owner()
