#!/usr/bin/env python3
"""Tests for the Qoder AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.qoder import QoderIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .qoder config root."""
    qoder_dir = tmp_path / ".qoder"
    qoder_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.qoder.Path.home",
        return_value=fake_home,
    )


def _write_settings(fake_home: Path, hooks: dict) -> None:
    settings_path = fake_home / ".qoder" / "settings.json"
    settings_path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_tool_info():
    assert QoderIntegration().get_tool_info() == ("qoder", "Qoder")


def test_settings_path_under_qoder(patched_home):
    with patched_home:
        assert QoderIntegration().get_settings_path() == (Path.home() / ".qoder" / "settings.json")


def test_config_dir_is_qoder(patched_home):
    with patched_home:
        assert QoderIntegration().get_config_dir() == Path.home() / ".qoder"


def test_setup_adds_all_hooks(fake_home: Path, patched_home):
    with patched_home:
        ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
        hooks = settings["hooks"]
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm play done"
        assert hooks["SessionEnd"][0]["hooks"][0]["command"] == "bgm stop"
        assert hooks["Notification"][0]["matcher"] == "permission_prompt"
        assert hooks["Notification"][0]["hooks"][0]["command"] == "bgm play notification 0"
        # Resume hook: fires after the user answers a permission prompt;
        # bgm play work 0 is idempotent, so it only switches back to work
        # (never restarts an already playing track).
        assert hooks["PostToolUse"][0]["hooks"][0]["command"] == "bgm play work 0"


def test_setup_keeps_other_settings_and_hooks(fake_home: Path, patched_home):
    _write_settings(fake_home, {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]})
    settings_path = fake_home / ".qoder" / "settings.json"
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    raw["model"] = "some-model"
    settings_path.write_text(json.dumps(raw), encoding="utf-8")

    with patched_home:
        ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["model"] == "some-model"
    assert settings["hooks"]["PreToolUse"] == [{"hooks": [{"type": "command", "command": "x"}]}]
    assert "PostToolUse" in settings["hooks"]


def test_setup_cleanup_roundtrip(fake_home: Path, patched_home):
    with patched_home:
        integration = QoderIntegration()
        assert not integration.is_configured()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_configured()
        assert integration.is_up_to_date()

        ok, _ = integration.perform_cleanup()
        assert ok
        assert not integration.is_configured()


def test_cleanup_removes_only_bgm_hooks(fake_home: Path, patched_home):
    _write_settings(fake_home, {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]})
    settings_path = fake_home / ".qoder" / "settings.json"

    with patched_home:
        ok, _ = QoderIntegration().perform_setup()
        assert ok
        ok, _ = QoderIntegration().perform_cleanup()
        assert ok
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "PostToolUse" not in settings["hooks"]
    assert settings["hooks"]["PreToolUse"] == [{"hooks": [{"type": "command", "command": "x"}]}]


def test_registry_returns_qoder():
    integration = IntegrationRegistry.get_integration_by_id("qoder")
    assert isinstance(integration, QoderIntegration)
