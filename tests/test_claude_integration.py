#!/usr/bin/env python3
"""Tests for the Claude Code AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.claude import ClaudeIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry

#: Deterministic stand-in for the bgm executable; hook commands are built
#: from ``shutil.which("bgm")``, which would otherwise leak the developer
#: machine's real path into assertions.
FAKE_BGM = "/fake/bin/bgm"

#: A handler owned by another tool (it2), used to prove setup keeps it.
OTHER_HANDLER = {"type": "command", "command": "/opt/homebrew/bin/it2 hook"}

WINDOWS_BGM = r"C:\Users\Jie\Scripts\bgm.exe"
WINDOWS_BGM_COMMAND = r"'C:\Users\Jie\Scripts\bgm.exe' hook stop"


@pytest.fixture(autouse=True)
def _patch_bgm_which():
    """Resolve bgm to a fixed absolute path for every test in this module."""
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.claude.shutil.which",
        return_value=FAKE_BGM,
    ):
        yield


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .claude config root."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.claude.Path.home",
        return_value=fake_home,
    )


def _settings_path(fake_home: Path) -> Path:
    return fake_home / ".claude" / "settings.json"


def _write_settings(fake_home: Path, settings: dict) -> None:
    _settings_path(fake_home).write_text(json.dumps(settings), encoding="utf-8")


def _read_settings(fake_home: Path) -> dict:
    data = json.loads(_settings_path(fake_home).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _other_tool_settings() -> dict:
    """A settings file where another tool hooks every event bgm manages."""
    return {
        "model": "claude-sonnet-4",
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "UserPromptSubmit": [{"hooks": [OTHER_HANDLER]}],
            "Stop": [{"hooks": [OTHER_HANDLER]}],
            "SessionEnd": [{"hooks": [OTHER_HANDLER]}],
            "Notification": [{"matcher": "permission_prompt", "hooks": [OTHER_HANDLER]}],
            "PreToolUse": [{"hooks": [OTHER_HANDLER]}],
            "PostToolUse": [{"hooks": [OTHER_HANDLER]}],
            "PostToolUseFailure": [{"hooks": [OTHER_HANDLER]}],
        },
    }


def test_tool_info():
    assert ClaudeIntegration().get_tool_info() == ("claude", "Claude Code")


def test_settings_path_under_claude(patched_home):
    with patched_home:
        assert ClaudeIntegration().get_settings_path() == (
            Path.home() / ".claude" / "settings.json"
        )


def test_setup_keeps_other_tool_handlers(fake_home: Path, patched_home):
    _write_settings(fake_home, _other_tool_settings())

    with patched_home:
        ok, _ = ClaudeIntegration().perform_setup()
        assert ok
        settings = _read_settings(fake_home)

    hooks = settings["hooks"]
    assert settings["model"] == "claude-sonnet-4"
    assert settings["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert hooks["PreToolUse"] == [{"hooks": [OTHER_HANDLER]}]
    assert len(hooks["PostToolUse"]) == 2
    assert hooks["PostToolUse"][0] == {"hooks": [OTHER_HANDLER]}
    assert hooks["PostToolUse"][1]["hooks"][0]["command"] == f"{FAKE_BGM} resume"
    assert len(hooks["PostToolUseFailure"]) == 2
    assert hooks["PostToolUseFailure"][0] == {"hooks": [OTHER_HANDLER]}
    assert hooks["PostToolUseFailure"][1]["hooks"][0]["command"] == f"{FAKE_BGM} resume"

    for event in ("UserPromptSubmit", "Stop", "SessionEnd"):
        assert hooks[event][0] == {"hooks": [OTHER_HANDLER]}
        assert len(hooks[event]) == 2
        assert len(hooks[event][1]["hooks"]) == 1

    assert hooks["UserPromptSubmit"][1]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"
    assert hooks["Stop"][1]["hooks"][0]["command"] == f"{FAKE_BGM} hook stop"
    assert hooks["SessionEnd"][1]["hooks"][0]["command"] == f"{FAKE_BGM} stop"

    notification = hooks["Notification"]
    assert notification[0] == {"matcher": "permission_prompt", "hooks": [OTHER_HANDLER]}
    assert notification[1]["matcher"] == "permission_prompt"
    assert notification[1]["hooks"][0]["command"] == f"{FAKE_BGM} play notification 0"
    assert notification[2]["matcher"] == "idle_prompt"
    assert notification[2]["hooks"][0]["command"] == f"{FAKE_BGM} hook idle"


def test_setup_keeps_other_handlers_inside_a_mixed_group(fake_home: Path, patched_home):
    _write_settings(
        fake_home,
        {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {"type": "command", "command": "bgm play done"},
                            OTHER_HANDLER,
                        ]
                    }
                ]
            }
        },
    )

    with patched_home:
        ok, _ = ClaudeIntegration().perform_setup()
        assert ok
        settings = _read_settings(fake_home)

    stop_groups = settings["hooks"]["Stop"]
    assert stop_groups[0] == {"hooks": [OTHER_HANDLER]}
    assert stop_groups[1]["hooks"][0]["command"] == f"{FAKE_BGM} hook stop"


def test_setup_resumes_work_after_an_answered_prompt(fake_home: Path, patched_home):
    """Both tool outcomes must be wired to resume; the music itself is covered by test_resume."""
    with patched_home:
        integration = ClaudeIntegration()
        ok, _ = integration.perform_setup()
        assert ok
        hooks = _read_settings(fake_home)["hooks"]

        assert hooks["PostToolUse"] == [
            {"hooks": [{"type": "command", "command": f"{FAKE_BGM} resume"}]}
        ]
        assert hooks["PostToolUseFailure"] == [
            {"hooks": [{"type": "command", "command": f"{FAKE_BGM} resume"}]}
        ]

        ok, _ = integration.perform_cleanup()
        assert ok

    assert "hooks" not in _read_settings(fake_home)


def test_setup_then_cleanup_restores_other_tool_settings(fake_home: Path, patched_home):
    initial = _other_tool_settings()
    _write_settings(fake_home, initial)

    with patched_home:
        integration = ClaudeIntegration()
        assert not integration.is_configured()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_configured()
        assert integration.is_up_to_date()

        ok, _ = integration.perform_cleanup()
        assert ok
        assert not integration.is_configured()

    restored = _read_settings(fake_home)
    assert json.dumps(restored, sort_keys=True) == json.dumps(initial, sort_keys=True)


def test_cleanup_leaves_no_hooks_key_when_there_was_none(fake_home: Path, patched_home):
    initial = {"model": "claude-sonnet-4"}
    _write_settings(fake_home, initial)

    with patched_home:
        integration = ClaudeIntegration()
        ok, _ = integration.perform_setup()
        assert ok
        ok, _ = integration.perform_cleanup()
        assert ok

    assert _read_settings(fake_home) == initial


def test_cleanup_drops_event_keys_that_only_held_bgm_handlers(fake_home: Path, patched_home):
    initial = {"hooks": {"PreToolUse": [{"hooks": [OTHER_HANDLER]}]}}
    _write_settings(fake_home, initial)

    with patched_home:
        integration = ClaudeIntegration()
        ok, _ = integration.perform_setup()
        assert ok
        ok, _ = integration.perform_cleanup()
        assert ok

    assert _read_settings(fake_home) == initial


def test_legacy_bgm_group_ahead_of_other_handlers_is_migrated(fake_home: Path, patched_home):
    legacy_bgm = {"hooks": [{"type": "command", "command": "bgm play done"}]}
    _write_settings(
        fake_home,
        {"hooks": {"Stop": [legacy_bgm, {"hooks": [OTHER_HANDLER]}]}},
    )

    with patched_home:
        integration = ClaudeIntegration()
        ok, _ = integration.perform_setup()
        assert ok
        stop_groups = _read_settings(fake_home)["hooks"]["Stop"]
        ok, _ = integration.perform_cleanup()
        assert ok

    assert stop_groups[0] == {"hooks": [OTHER_HANDLER]}
    assert stop_groups[1]["hooks"][0]["command"] == f"{FAKE_BGM} hook stop"
    assert _read_settings(fake_home)["hooks"]["Stop"] == [{"hooks": [OTHER_HANDLER]}]


def test_setup_is_deterministic(fake_home: Path, patched_home):
    _write_settings(fake_home, _other_tool_settings())

    with patched_home:
        integration = ClaudeIntegration()
        ok, _ = integration.perform_setup()
        assert ok
        first = _read_settings(fake_home)

        ok, _ = integration.perform_setup()
        assert ok
        second = _read_settings(fake_home)
        assert integration.is_up_to_date()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_legacy_bare_command_config_is_upgraded(fake_home: Path, patched_home):
    _write_settings(
        fake_home,
        {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": "bgm play work 0"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": "bgm play done"}]}],
                "SessionEnd": [{"hooks": [{"type": "command", "command": "bgm stop"}]}],
                "Notification": [
                    {
                        "matcher": "permission_prompt",
                        "hooks": [{"type": "command", "command": "bgm play notification 0"}],
                    }
                ],
            }
        },
    )

    with patched_home:
        integration = ClaudeIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_up_to_date()

    hooks = _read_settings(fake_home)["hooks"]
    assert len(hooks["UserPromptSubmit"]) == 1
    assert len(hooks["Stop"]) == 1
    assert len(hooks["SessionEnd"]) == 1
    assert len(hooks["Notification"]) == 2
    assert len(hooks["PostToolUse"]) == 1
    assert len(hooks["PostToolUseFailure"]) == 1
    assert hooks["Stop"][0]["hooks"][0]["command"] == f"{FAKE_BGM} hook stop"
    assert hooks["Notification"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play notification 0"
    assert hooks["Notification"][1]["hooks"][0]["command"] == f"{FAKE_BGM} hook idle"
    assert hooks["PostToolUse"][0]["hooks"][0]["command"] == f"{FAKE_BGM} resume"


def test_setup_falls_back_to_bare_bgm_when_unresolvable(fake_home: Path, patched_home):
    """which() returning None must not fail setup -- bare bgm is the fallback."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.claude.shutil.which",
            return_value=None,
        ):
            ok, _ = ClaudeIntegration().perform_setup()
        assert ok
        settings = _read_settings(fake_home)

    hooks = settings["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
    assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm hook stop"


def test_setup_quotes_executable_path_with_spaces(fake_home: Path, patched_home):
    """An executable path containing spaces must stay owned by bgm."""
    spaced = "/fake bin/bgm"
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.claude.shutil.which",
            return_value=spaced,
        ):
            integration = ClaudeIntegration()
            ok, _ = integration.perform_setup()
            assert ok
            settings = _read_settings(fake_home)
            assert integration.is_up_to_date()

            ok, _ = integration.perform_cleanup()
            assert ok
            assert not integration.is_configured()

    hooks = settings["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == f"'{spaced}' play work 0"
    assert hooks["Stop"][0]["hooks"][0]["command"] == f"'{spaced}' hook stop"


def test_windows_style_executable_path_round_trips(fake_home: Path, patched_home):
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.claude.shutil.which",
            return_value=WINDOWS_BGM,
        ):
            integration = ClaudeIntegration()
            ok, _ = integration.perform_setup()
            assert ok
            settings = _read_settings(fake_home)
            assert settings["hooks"]["Stop"][0]["hooks"][0]["command"] == WINDOWS_BGM_COMMAND
            assert integration.is_up_to_date()

            ok, _ = integration.perform_setup()
            assert ok
            settings = _read_settings(fake_home)
            for event in ("UserPromptSubmit", "Stop", "SessionEnd"):
                assert len(settings["hooks"][event]) == 1
            assert len(settings["hooks"]["Notification"]) == 2

            ok, _ = integration.perform_cleanup()
            assert ok
            assert not integration.is_configured()

    assert "hooks" not in _read_settings(fake_home)


def test_registry_returns_claude():
    integration = IntegrationRegistry.get_integration_by_id("claude")
    assert isinstance(integration, ClaudeIntegration)
