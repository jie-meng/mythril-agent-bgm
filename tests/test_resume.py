#!/usr/bin/env python3
"""Tests for the bgm resume command."""

import contextlib
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from mythril_agent_bgm.commands.resume import resume
from mythril_agent_bgm.utils.common import save_state


def _invoke_resume(notification_playing: bool):
    """Invoke resume with the playback probe mocked; return the spawn mock."""
    with (
        mock.patch("mythril_agent_bgm.commands.resume.is_bgm_enabled", return_value=True),
        mock.patch(
            "mythril_agent_bgm.commands.resume.is_music_type_playing",
            side_effect=lambda music_type: notification_playing and music_type == "notification",
        ) as playing,
        mock.patch("mythril_agent_bgm.commands.resume.start_background_player") as start,
    ):
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    return start, playing


@contextlib.contextmanager
def _real_state(tmp_path: Path, process_alive: bool = True):
    """Run resume against a real state/PID pair isolated in tmp_path."""
    pid_file = tmp_path / "bgm_player.pid"
    pid_file.write_text("12345", encoding="utf-8")
    with (
        mock.patch("mythril_agent_bgm.commands.resume.is_bgm_enabled", return_value=True),
        mock.patch("mythril_agent_bgm.utils.common.get_config_dir", return_value=tmp_path),
        mock.patch("mythril_agent_bgm.commands.play.get_pid_file", return_value=pid_file),
        mock.patch(
            "mythril_agent_bgm.commands.play.ProcessManager.check_process_exists",
            return_value=process_alive,
        ),
        mock.patch("mythril_agent_bgm.commands.resume.start_background_player") as start,
    ):
        yield start


def test_resume_switches_to_work_while_notification_plays():
    start, playing = _invoke_resume(notification_playing=True)
    playing.assert_called_once_with("notification")
    start.assert_called_once_with("work", 0)


def test_resume_noop_when_notification_not_playing():
    start, _ = _invoke_resume(notification_playing=False)
    start.assert_not_called()


def test_resume_noop_when_work_playing(tmp_path: Path):
    with _real_state(tmp_path) as start:
        save_state("work")
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    start.assert_not_called()


def test_resume_noop_when_done_playing(tmp_path: Path):
    with _real_state(tmp_path) as start:
        save_state("done")
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    start.assert_not_called()


def test_resume_noop_when_done_finished(tmp_path: Path):
    with _real_state(tmp_path) as start:
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    start.assert_not_called()


def test_resume_noop_when_notification_state_is_stale(tmp_path: Path):
    """A notification state file with no live daemon must not start work."""
    with _real_state(tmp_path, process_alive=False) as start:
        save_state("notification")
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    start.assert_not_called()


def test_resume_detects_live_notification_daemon(tmp_path: Path):
    with _real_state(tmp_path) as start:
        save_state("notification")
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    start.assert_called_once_with("work", 0)


def test_resume_noop_when_bgm_disabled():
    with (
        mock.patch("mythril_agent_bgm.commands.resume.is_bgm_enabled", return_value=False),
        mock.patch("mythril_agent_bgm.commands.resume.is_music_type_playing", return_value=True),
        mock.patch("mythril_agent_bgm.commands.resume.start_background_player") as start,
    ):
        result = CliRunner().invoke(resume)
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_not_called()
