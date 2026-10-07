#!/usr/bin/env python3
"""Tests for the music state file and idempotent bgm play behavior."""

import sys
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.play import (
    _bgm_executable,
    is_music_type_playing,
    start_background_player,
)
from mythril_agent_bgm.utils.common import (
    get_state_file,
    save_state,
    load_state,
    clear_state,
)


@pytest.fixture
def patched_config_dir(tmp_path: Path):
    with mock.patch("mythril_agent_bgm.utils.common.get_config_dir", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def patched_player(tmp_path: Path):
    """Patch state/pid file paths, process checks and subprocess spawning."""
    tmp_path.joinpath("bgm_player.pid").write_text("12345", encoding="utf-8")
    with (
        mock.patch(
            "mythril_agent_bgm.commands.play.get_pid_file",
            return_value=tmp_path / "bgm_player.pid",
        ),
        mock.patch(
            "mythril_agent_bgm.commands.play.get_lock_file",
            return_value=tmp_path / "bgm_player.lock",
        ),
        mock.patch("mythril_agent_bgm.utils.common.get_config_dir", return_value=tmp_path),
        mock.patch(
            "mythril_agent_bgm.commands.play.ProcessManager.check_process_exists",
            side_effect=lambda pid: True,
        ),
    ):
        yield


def test_save_load_clear_state(patched_config_dir):
    assert load_state() == ""
    save_state("notification")
    assert load_state() == "notification"
    assert get_state_file().exists()
    clear_state()
    assert load_state() == ""
    assert not get_state_file().exists()


def test_load_state_missing_file(patched_config_dir):
    assert load_state() == ""


def test_is_music_type_playing(patched_player):
    assert not is_music_type_playing("work")
    save_state("notification")
    assert not is_music_type_playing("work")
    assert is_music_type_playing("notification")


def test_is_music_type_playing_stale_state(patched_player, tmp_path: Path):
    # State says work but no daemon is alive: must not count as playing,
    # otherwise a stale state file would silence play forever.
    save_state("work")
    tmp_path.joinpath("bgm_player.pid").write_text("99999", encoding="utf-8")
    with mock.patch(
        "mythril_agent_bgm.commands.play.ProcessManager.check_process_exists",
        return_value=False,
    ):
        assert not is_music_type_playing("work")


def test_play_noop_when_same_type_playing(patched_player):
    save_state("work")
    with mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen:
        start_background_player("work", 0)
    popen.assert_not_called()


def test_play_switches_when_different_type_playing(patched_player):
    save_state("notification")
    with mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen:
        start_background_player("work", 0)
    popen.assert_called_once()


def test_play_starts_when_nothing_playing(patched_player):
    with mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen:
        start_background_player("work", 0)
    popen.assert_called_once()


def test_play_noop_when_notification_playing(patched_player):
    # A repeated permission prompt must not restart the notification loop.
    save_state("notification")
    with mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen:
        start_background_player("notification", 0)
    popen.assert_not_called()


def test_play_spawns_absolute_bgm_from_path(patched_player):
    # Host apps run hooks under a sanitized PATH, so the daemon must be
    # spawned with the resolved absolute executable, never the bare name.
    bgm_path = "/Users/tester/.pyenv/shims/bgm"
    with (
        mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen,
        mock.patch(
            "mythril_agent_bgm.commands.play.shutil.which",
            return_value=bgm_path,
        ),
    ):
        start_background_player("work", 0)
    popen.assert_called_once()
    assert popen.call_args[0][0][0] == bgm_path


def test_play_spawns_absolute_bgm_from_argv0(patched_player):
    # With no PATH hit, an absolute sys.argv[0] (how the hook invokes bgm)
    # is the only way to spawn the daemon.
    bgm_path = "/Users/tester/.local/bin/bgm"
    with (
        mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen,
        mock.patch("mythril_agent_bgm.commands.play.shutil.which", return_value=None),
        mock.patch.object(sys, "argv", [bgm_path, "play", "work"]),
    ):
        start_background_player("work", 0)
    popen.assert_called_once()
    assert popen.call_args[0][0][0] == bgm_path


def test_play_ignores_absolute_argv0_that_is_not_bgm(patched_player):
    # Running the local dev entry point (`python /repo/main.py play work 0`)
    # makes argv[0] an absolute path that is not executable bgm. Trusting it
    # blindly would spawn main.py and fail with PermissionError, a regression
    # against the bare `bgm` fallback.
    with (
        mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen,
        mock.patch("mythril_agent_bgm.commands.play.shutil.which", return_value=None),
        mock.patch.object(sys, "argv", ["/repo/main.py", "play", "work"]),
    ):
        start_background_player("work", 0)
    popen.assert_called_once()
    assert popen.call_args[0][0][0] == "bgm"


def test_bgm_executable_with_empty_argv():
    # sys.argv can be empty (embedded interpreters); the guard must not raise.
    with (
        mock.patch("mythril_agent_bgm.commands.play.shutil.which", return_value=None),
        mock.patch.object(sys, "argv", []),
    ):
        assert _bgm_executable() == "bgm"


def test_play_falls_back_to_bare_bgm_name(patched_player):
    # Neither lookup resolves: keep the previous behavior instead of
    # refusing to play.
    with (
        mock.patch("mythril_agent_bgm.commands.play.subprocess.Popen") as popen,
        mock.patch("mythril_agent_bgm.commands.play.shutil.which", return_value=None),
        mock.patch.object(sys, "argv", ["bgm", "play", "work"]),
    ):
        start_background_player("work", 0)
    popen.assert_called_once()
    assert popen.call_args[0][0] == ["bgm", "play", "--daemon", "work", "0"]
