#!/usr/bin/env python3
"""Tests for the CodeBuddy Code AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.codebuddy import CodeBuddyIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .codebuddy config root."""
    codebuddy_dir = tmp_path / ".codebuddy"
    codebuddy_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.codebuddy.Path.home",
        return_value=fake_home,
    )


def _write_settings(fake_home: Path, hooks: dict) -> None:
    settings_path = fake_home / ".codebuddy" / "settings.json"
    settings_path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_tool_info():
    assert CodeBuddyIntegration().get_tool_info() == ("codebuddy", "CodeBuddy Code")


def test_settings_path_under_codebuddy(patched_home):
    with patched_home:
        assert CodeBuddyIntegration().get_settings_path() == (
            Path.home() / ".codebuddy" / "settings.json"
        )


def test_config_dir_is_codebuddy(patched_home):
    with patched_home:
        assert CodeBuddyIntegration().get_config_dir() == Path.home() / ".codebuddy"


def test_setup_adds_all_hooks(fake_home: Path, patched_home):
    with patched_home:
        ok, _ = CodeBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(
            (fake_home / ".codebuddy" / "settings.json").read_text(encoding="utf-8")
        )
        hooks = settings["hooks"]
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm play done"
        assert hooks["SessionEnd"][0]["hooks"][0]["command"] == "bgm stop"
        assert hooks["Notification"][0]["matcher"] == "permission_prompt"
        assert hooks["Notification"][0]["hooks"][0]["command"] == "bgm play notification 0"
        # AskUserQuestion dialogs emit no Notification event (the
        # elicitation_dialog matcher is never fired), so the alert rides on
        # PreToolUse, which runs right before the question dialog appears.
        assert hooks["PreToolUse"][0]["matcher"] == "AskUserQuestion"
        assert hooks["PreToolUse"][0]["hooks"][0]["command"] == "bgm play notification 0"
        # Resume hooks: fire after the user answers a permission prompt /
        # question dialog; bgm play work 0 is idempotent, so it only
        # switches back to work (never restarts an already playing track).
        for event in ("PostToolUse", "ElicitationResult", "PermissionDenied"):
            assert event in hooks
            assert hooks[event][0]["hooks"][0]["command"] == "bgm play work 0"


def test_setup_keeps_other_settings_and_hooks(fake_home: Path, patched_home):
    _write_settings(fake_home, {"ConfigChange": [{"hooks": [{"type": "command", "command": "x"}]}]})
    settings_path = fake_home / ".codebuddy" / "settings.json"
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    raw["model"] = "hy3"
    settings_path.write_text(json.dumps(raw), encoding="utf-8")

    with patched_home:
        ok, _ = CodeBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["model"] == "hy3"
    assert settings["hooks"]["ConfigChange"] == [{"hooks": [{"type": "command", "command": "x"}]}]
    assert "PostToolUse" in settings["hooks"]


def test_setup_cleanup_roundtrip(fake_home: Path, patched_home):
    with patched_home:
        integration = CodeBuddyIntegration()
        assert not integration.is_configured()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_configured()
        assert integration.is_up_to_date()

        ok, _ = integration.perform_cleanup()
        assert ok
        assert not integration.is_configured()


def test_cleanup_removes_only_bgm_hooks(fake_home: Path, patched_home):
    _write_settings(fake_home, {"ConfigChange": [{"hooks": [{"type": "command", "command": "x"}]}]})
    settings_path = fake_home / ".codebuddy" / "settings.json"

    with patched_home:
        ok, _ = CodeBuddyIntegration().perform_setup()
        assert ok
        ok, _ = CodeBuddyIntegration().perform_cleanup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "PostToolUse" not in settings["hooks"]
    assert "PreToolUse" not in settings["hooks"]
    assert settings["hooks"]["ConfigChange"] == [{"hooks": [{"type": "command", "command": "x"}]}]


def test_up_to_date_detects_missing_resume_hook(fake_home: Path, patched_home):
    # Simulate the pre-resume config: notification hook but no resume hooks.
    _write_settings(
        fake_home,
        {
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "bgm play done"}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": "bgm stop"}]}],
            "Notification": [
                {
                    "matcher": "permission_prompt",
                    "hooks": [{"type": "command", "command": "bgm play notification 0"}],
                }
            ],
        },
    )
    with patched_home:
        integration = CodeBuddyIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()


def test_up_to_date_detects_missing_ask_user_question_hook(fake_home: Path, patched_home):
    """A config that predates the AskUserQuestion alert must be seen as outdated."""
    integration = CodeBuddyIntegration()
    _write_settings(fake_home, {})
    with patched_home:
        ok, _ = integration.perform_setup()
        assert ok
        settings_path = fake_home / ".codebuddy" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        # Drop only the AskUserQuestion alert, keep everything else.
        settings["hooks"].pop("PreToolUse")
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        assert integration.is_configured()
        assert not integration.is_up_to_date()


def test_registry_returns_codebuddy():
    integration = IntegrationRegistry.get_integration_by_id("codebuddy")
    assert isinstance(integration, CodeBuddyIntegration)
