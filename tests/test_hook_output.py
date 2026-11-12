#!/usr/bin/env python3
"""Hook-invoked commands must stay quiet on a non-interactive stdout.

Host apps (CodeBuddy, ZCode, ...) run hooks through pipes and surface
every stdout line in their session. Informational output is therefore
limited to an interactive terminal, and pygame's import banner is always
hidden.
"""

import os
import subprocess
import sys
from unittest import mock

import pytest
from click.testing import CliRunner

from mythril_agent_bgm.commands.play import play, start_background_player
from mythril_agent_bgm.commands.stop import stop
from mythril_agent_bgm.utils.common import is_interactive


class _FakeStdout:
    """Minimal stand-in exposing only what is_interactive() reads."""

    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_is_interactive_follows_stdout(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _FakeStdout(True))
    assert is_interactive() is True

    monkeypatch.setattr(sys, "stdout", _FakeStdout(False))
    assert is_interactive() is False


def test_disabled_play_is_silent_on_pipe():
    with (
        mock.patch("mythril_agent_bgm.commands.play.is_bgm_enabled", return_value=False),
        mock.patch("mythril_agent_bgm.commands.play.is_interactive", return_value=False),
    ):
        result = CliRunner().invoke(play, ["work", "0"])
    assert result.exit_code == 0
    assert result.stdout == ""


def test_disabled_play_keeps_hint_on_tty():
    with (
        mock.patch("mythril_agent_bgm.commands.play.is_bgm_enabled", return_value=False),
        mock.patch("mythril_agent_bgm.commands.play.is_interactive", return_value=True),
    ):
        result = CliRunner().invoke(play, ["work", "0"])
    assert result.exit_code == 0
    assert "AI BGM is disabled" in result.stdout


@pytest.mark.parametrize("killed", [False, True])
def test_stop_is_silent_on_pipe(killed, tmp_path):
    with (
        mock.patch("mythril_agent_bgm.commands.stop.FileLock"),
        mock.patch(
            "mythril_agent_bgm.commands.stop.get_lock_file",
            return_value=tmp_path / "bgm_player.lock",
        ),
        mock.patch("mythril_agent_bgm.commands.stop.kill_existing_player", return_value=killed),
        mock.patch("mythril_agent_bgm.commands.stop.is_interactive", return_value=False),
    ):
        result = CliRunner().invoke(stop)
    assert result.exit_code == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("killed", "expected"),
    [
        (False, "No BGM player is currently running"),
        (True, "Stopped BGM player"),
    ],
)
def test_stop_keeps_message_on_tty(killed, expected, tmp_path):
    with (
        mock.patch("mythril_agent_bgm.commands.stop.FileLock"),
        mock.patch(
            "mythril_agent_bgm.commands.stop.get_lock_file",
            return_value=tmp_path / "bgm_player.lock",
        ),
        mock.patch("mythril_agent_bgm.commands.stop.kill_existing_player", return_value=killed),
        mock.patch("mythril_agent_bgm.commands.stop.is_interactive", return_value=True),
    ):
        result = CliRunner().invoke(stop)
    assert result.exit_code == 0
    assert expected in result.stdout


@pytest.fixture
def patched_player(tmp_path):
    """Patch the daemon-start path so no process, file, or lock is real."""
    pid_file = tmp_path / "bgm_player.pid"
    pid_file.write_text("12345", encoding="utf-8")
    with (
        mock.patch(
            "mythril_agent_bgm.commands.play.get_lock_file",
            return_value=tmp_path / "bgm_player.lock",
        ),
        mock.patch("mythril_agent_bgm.commands.play.get_pid_file", return_value=pid_file),
        mock.patch("mythril_agent_bgm.commands.play.is_music_type_playing", return_value=False),
        mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen"),
        mock.patch("mythril_agent_bgm.commands.play.wait_for_daemon_pid"),
        mock.patch("mythril_agent_bgm.commands.play.wait_for_playback_state"),
        mock.patch("mythril_agent_bgm.commands.play.time.sleep"),
        mock.patch("mythril_agent_bgm.commands.play.FileLock"),
    ):
        yield


@pytest.mark.parametrize("previous_pid", [None, 999])
def test_start_is_silent_on_pipe(patched_player, previous_pid, capsys):
    with (
        mock.patch("mythril_agent_bgm.commands.play.is_interactive", return_value=False),
        mock.patch(
            "mythril_agent_bgm.commands.play.kill_existing_process",
            return_value=previous_pid,
        ),
    ):
        start_background_player("done", 1)
    assert capsys.readouterr().out == ""


def test_start_keeps_messages_on_tty(patched_player, capsys):
    with (
        mock.patch("mythril_agent_bgm.commands.play.is_interactive", return_value=True),
        mock.patch("mythril_agent_bgm.commands.play.kill_existing_process", return_value=999),
    ):
        start_background_player("done", 1)
    output = capsys.readouterr().out
    assert "Stopped previous BGM player" in output
    assert "BGM player started in background" in output
    assert "Background player PID: 12345" in output


def test_importing_play_has_no_pygame_banner():
    env = dict(os.environ)
    env.pop("PYGAME_HIDE_SUPPORT_PROMPT", None)
    result = subprocess.run(
        [sys.executable, "-c", "import mythril_agent_bgm.commands.play"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_cli_help_has_no_pygame_banner():
    env = dict(os.environ)
    env.pop("PYGAME_HIDE_SUPPORT_PROMPT", None)
    result = subprocess.run(
        [sys.executable, "-m", "mythril_agent_bgm.cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "pygame" not in result.stdout.lower()
