#!/usr/bin/env python3
"""Tests for the WorkBuddy AI integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry
from mythril_agent_bgm.commands.integrations.workbuddy import (
    CONFIG_DIR_ENV,
    WorkBuddyIntegration,
)


@pytest.fixture(autouse=True)
def _clear_config_dir_env(monkeypatch):
    """Keep the ambient WORKBUDDY_CONFIG_DIR out of the path-resolution tests."""
    monkeypatch.delenv(CONFIG_DIR_ENV, raising=False)


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .workbuddy-ai config root."""
    (tmp_path / ".workbuddy-ai").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.workbuddy.Path.home",
        return_value=fake_home,
    )


def _write_settings(config_dir: Path, hooks: dict) -> None:
    (config_dir / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_tool_info():
    assert WorkBuddyIntegration().get_tool_info() == ("workbuddy", "WorkBuddy AI")


def test_settings_path_under_workbuddy_ai(patched_home):
    with patched_home:
        assert WorkBuddyIntegration().get_settings_path() == (
            Path.home() / ".workbuddy-ai" / "settings.json"
        )


def test_config_dir_is_workbuddy_ai(patched_home):
    with patched_home:
        assert WorkBuddyIntegration().get_config_dir() == Path.home() / ".workbuddy-ai"


def test_falls_back_to_legacy_workbuddy_dir(tmp_path: Path):
    """Only ~/.workbuddy exists (non-overseas edition)."""
    (tmp_path / ".workbuddy").mkdir(parents=True)
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.workbuddy.Path.home",
        return_value=tmp_path,
    ):
        integration = WorkBuddyIntegration()
        assert integration.get_config_dir() == tmp_path / ".workbuddy"
        assert integration.get_settings_path() == tmp_path / ".workbuddy" / "settings.json"


def test_defaults_to_workbuddy_ai_when_nothing_exists(tmp_path: Path):
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.workbuddy.Path.home",
        return_value=tmp_path,
    ):
        assert WorkBuddyIntegration().get_config_dir() == tmp_path / ".workbuddy-ai"


def test_env_var_override_wins(tmp_path: Path, monkeypatch):
    """The desktop app injects WORKBUDDY_CONFIG_DIR; it must take priority."""
    override = tmp_path / "custom-config"
    override.mkdir()
    (tmp_path / ".workbuddy-ai").mkdir()
    monkeypatch.setenv(CONFIG_DIR_ENV, str(override))

    with mock.patch(
        "mythril_agent_bgm.commands.integrations.workbuddy.Path.home",
        return_value=tmp_path,
    ):
        assert WorkBuddyIntegration().get_settings_path() == override / "settings.json"


def test_setup_adds_all_hooks(fake_home: Path, patched_home):
    with patched_home:
        ok, _ = WorkBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(
            (fake_home / ".workbuddy-ai" / "settings.json").read_text(encoding="utf-8")
        )
        hooks = settings["hooks"]
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm play done"
        assert hooks["SessionEnd"][0]["hooks"][0]["command"] == "bgm stop"
        assert hooks["Notification"][0]["matcher"] == "permission_prompt"
        assert hooks["Notification"][0]["hooks"][0]["command"] == "bgm play notification 0"
        for event in ("PostToolUse", "ElicitationResult", "PermissionDenied"):
            assert event in hooks
            assert hooks[event][0]["hooks"][0]["command"] == "bgm play work 0"


def test_setup_keeps_other_settings_and_hooks(fake_home: Path, patched_home):
    _write_settings(
        fake_home / ".workbuddy-ai",
        {"ConfigChange": [{"hooks": [{"type": "command", "command": "x"}]}]},
    )
    settings_path = fake_home / ".workbuddy-ai" / "settings.json"
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    raw["enabledPlugins"] = {"agent-browser@codebuddy-plugins-official": True}
    settings_path.write_text(json.dumps(raw), encoding="utf-8")

    with patched_home:
        ok, _ = WorkBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert settings["enabledPlugins"] == {"agent-browser@codebuddy-plugins-official": True}
    assert settings["hooks"]["ConfigChange"] == [{"hooks": [{"type": "command", "command": "x"}]}]
    assert "PostToolUse" in settings["hooks"]


def test_setup_cleanup_roundtrip(fake_home: Path, patched_home):
    with patched_home:
        integration = WorkBuddyIntegration()
        assert not integration.is_configured()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_configured()
        assert integration.is_up_to_date()

        ok, _ = integration.perform_cleanup()
        assert ok
        assert not integration.is_configured()


def test_cleanup_removes_only_bgm_hooks(fake_home: Path, patched_home):
    _write_settings(
        fake_home / ".workbuddy-ai",
        {"ConfigChange": [{"hooks": [{"type": "command", "command": "x"}]}]},
    )
    settings_path = fake_home / ".workbuddy-ai" / "settings.json"

    with patched_home:
        ok, _ = WorkBuddyIntegration().perform_setup()
        assert ok
        ok, _ = WorkBuddyIntegration().perform_cleanup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert "PostToolUse" not in settings["hooks"]
    assert settings["hooks"]["ConfigChange"] == [{"hooks": [{"type": "command", "command": "x"}]}]


def test_setup_reports_missing_config_dir(tmp_path: Path):
    """A machine without WorkBuddy installed must be reported as such."""
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.workbuddy.Path.home",
        return_value=empty_home,
    ):
        ok, message = WorkBuddyIntegration().perform_setup()
    assert not ok
    assert "WorkBuddy AI" in message


def test_registry_returns_workbuddy():
    integration = IntegrationRegistry.get_integration_by_id("workbuddy")
    assert isinstance(integration, WorkBuddyIntegration)


def test_env_var_constant_matches_desktop_app():
    """Guard the env var name the WorkBuddy desktop app actually injects."""
    assert CONFIG_DIR_ENV == "WORKBUDDY_CONFIG_DIR"
