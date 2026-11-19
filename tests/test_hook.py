#!/usr/bin/env python3
"""Tests for the bgm hook entry points."""

import json
from unittest import mock

import pytest
from click.testing import CliRunner

from mythril_agent_bgm.cli import cli
from mythril_agent_bgm.commands.hook import _read_stdin_payload, hook


class _TtyStdin:
    """Terminal stand-in: reading it would block, so it must not be read."""

    def isatty(self) -> bool:
        return True

    def read(self) -> str:
        raise AssertionError("a TTY stdin must not be read")


@pytest.fixture(autouse=True)
def _owner_dir(tmp_path, monkeypatch):
    """Keep the ownership file and lock inside the test's temporary directory."""
    monkeypatch.setattr("mythril_agent_bgm.commands.hook.get_config_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "mythril_agent_bgm.commands.hook.get_lock_file",
        lambda: tmp_path / "bgm_player.lock",
    )


def _owner_file(tmp_path):
    return tmp_path / "bgm_work_owner"


def _invoke(command, input_text=None, bgm_enabled=True, work_playing=False):
    """Invoke a hook subcommand with playback mocked; return (result, start)."""
    with (
        mock.patch(
            "mythril_agent_bgm.commands.hook.is_bgm_enabled",
            return_value=bgm_enabled,
        ),
        mock.patch(
            "mythril_agent_bgm.commands.hook.is_music_type_playing",
            return_value=work_playing,
        ),
        mock.patch("mythril_agent_bgm.commands.hook.start_background_player") as start,
    ):
        result = CliRunner().invoke(hook, command, input=input_text)
    return result, start


def _invoke_end(input_text, bgm_enabled=True):
    """Invoke ``hook end`` with both the player and playback mocked."""
    with (
        mock.patch(
            "mythril_agent_bgm.commands.hook.is_bgm_enabled",
            return_value=bgm_enabled,
        ),
        mock.patch("mythril_agent_bgm.commands.hook.kill_existing_player") as kill,
    ):
        result = CliRunner().invoke(hook, ["end"], input=input_text)
    return result, kill


def test_stop_keeps_work_while_background_tasks_run():
    payload = json.dumps({"background_tasks": [{"type": "subagent", "id": "a1"}]})
    result, start = _invoke(["stop"], input_text=payload)
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_called_once_with("work", 0)


def test_stop_plays_done_without_background_tasks():
    result, start = _invoke(["stop"], input_text=json.dumps({"background_tasks": []}))
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_called_once_with("done", 1)


def test_stop_ignores_session_crons():
    payload = json.dumps({"background_tasks": [], "session_crons": [{"id": "c1"}]})
    result, start = _invoke(["stop"], input_text=payload)
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_called_once_with("done", 1)


@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "not-json",
        "{}",
        "[]",
        '{"background_tasks": null}',
        '{"background_tasks": "subagent"}',
    ],
)
def test_stop_treats_unusable_input_as_no_background_tasks(stdin):
    result, start = _invoke(["stop"], input_text=stdin)
    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    start.assert_called_once_with("done", 1)


def test_read_stdin_payload_without_stdin():
    with mock.patch("mythril_agent_bgm.commands.hook.sys.stdin", None):
        assert _read_stdin_payload() == {}


def test_read_stdin_payload_on_a_terminal():
    with mock.patch("mythril_agent_bgm.commands.hook.sys.stdin", _TtyStdin()):
        assert _read_stdin_payload() == {}


def test_work_starts_work_music_and_claims_ownership(tmp_path):
    result, start = _invoke(["work"], input_text=json.dumps({"session_id": "session-a"}))
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_called_once_with("work", 0)
    assert _owner_file(tmp_path).read_text() == "session-a"


def test_work_survives_an_unwritable_owner_file(tmp_path):
    with mock.patch("pathlib.Path.write_text", side_effect=OSError):
        result, start = _invoke(["work"], input_text=json.dumps({"session_id": "session-a"}))
    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    start.assert_called_once_with("work", 0)


def test_work_does_not_restart_track_already_playing(tmp_path):
    result, start = _invoke(
        ["work"], input_text=json.dumps({"session_id": "session-a"}), work_playing=True
    )
    assert result.exit_code == 0
    start.assert_not_called()
    assert _owner_file(tmp_path).read_text() == "session-a"


def test_stop_with_background_tasks_claims_ownership(tmp_path):
    payload = json.dumps({"session_id": "session-a", "background_tasks": [{"type": "subagent"}]})
    result, start = _invoke(["stop"], input_text=payload)
    assert result.exit_code == 0
    start.assert_called_once_with("work", 0)
    assert _owner_file(tmp_path).read_text() == "session-a"


def test_stop_leaves_another_sessions_music_alone(tmp_path):
    _owner_file(tmp_path).write_text("session-a")
    payload = json.dumps({"session_id": "session-b", "background_tasks": []})
    result, start = _invoke(["stop"], input_text=payload)
    assert result.exit_code == 0
    start.assert_not_called()
    assert _owner_file(tmp_path).read_text() == "session-a"


def test_stop_plays_done_for_the_owning_session(tmp_path):
    _owner_file(tmp_path).write_text("session-a")
    payload = json.dumps({"session_id": "session-a", "background_tasks": []})
    result, start = _invoke(["stop"], input_text=payload)
    assert result.exit_code == 0
    start.assert_called_once_with("done", 1)
    assert not _owner_file(tmp_path).exists()


def test_idle_leaves_another_sessions_music_alone(tmp_path):
    _owner_file(tmp_path).write_text("session-a")
    result, start = _invoke(
        ["idle"], input_text=json.dumps({"session_id": "session-b"}), work_playing=True
    )
    assert result.exit_code == 0
    start.assert_not_called()


def test_end_stops_music_for_the_owning_session(tmp_path):
    _owner_file(tmp_path).write_text("session-a")
    result, kill = _invoke_end(json.dumps({"session_id": "session-a"}))
    assert result.exit_code == 0
    assert result.stdout == ""
    kill.assert_called_once_with()
    assert not _owner_file(tmp_path).exists()


def test_end_stops_music_even_when_bgm_is_disabled(tmp_path):
    """Ending a session must not leave a daemon looping after ``bgm disable``."""
    _owner_file(tmp_path).write_text("session-a")
    result, kill = _invoke_end(json.dumps({"session_id": "session-a"}), bgm_enabled=False)
    assert result.exit_code == 0
    kill.assert_called_once_with()
    assert not _owner_file(tmp_path).exists()


def test_end_leaves_another_sessions_owner_untouched(tmp_path):
    _owner_file(tmp_path).write_text("session-a")
    result, kill = _invoke_end(json.dumps({"session_id": "session-b"}))
    assert result.exit_code == 0
    kill.assert_not_called()
    assert _owner_file(tmp_path).read_text() == "session-a"


def test_end_without_an_owner_does_nothing(tmp_path):
    result, kill = _invoke_end(json.dumps({"session_id": "session-a"}))
    assert result.exit_code == 0
    kill.assert_not_called()
    assert not _owner_file(tmp_path).exists()


def test_idle_plays_done_while_work_is_playing():
    result, start = _invoke(["idle"], work_playing=True)
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_called_once_with("done", 1)


def test_idle_leaves_other_states_untouched():
    result, start = _invoke(["idle"], work_playing=False)
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_not_called()


@pytest.mark.parametrize("command", [["stop"], ["idle"], ["work"]])
def test_disabled_bgm_does_nothing(command):
    result, start = _invoke(
        command,
        input_text=json.dumps({"background_tasks": [{"id": "a1"}]}),
        bgm_enabled=False,
        work_playing=True,
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    start.assert_not_called()


def test_cli_registers_hook():
    assert cli.commands["hook"] is hook


def test_hook_help_lists_phases():
    with mock.patch("mythril_agent_bgm.cli.ensure_user_config_dir"):
        result = CliRunner().invoke(cli, ["hook", "--help"])
    assert result.exit_code == 0
    for name in ("work", "stop", "idle", "end"):
        assert f"\n  {name} " in result.stdout
