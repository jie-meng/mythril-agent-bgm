#!/usr/bin/env python3
"""Tests for the Qoder AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.qoder import QoderIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry

#: Deterministic stand-in for the bgm executable; hook commands are built
#: from ``shutil.which("bgm")``, which would otherwise leak the developer
#: machine's real path into assertions.
FAKE_BGM = "/fake/bin/bgm"


@pytest.fixture(autouse=True)
def _patch_bgm_which():
    """Resolve bgm to a fixed absolute path for every test in this module."""
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
        return_value=FAKE_BGM,
    ):
        yield


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
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play done"
        assert hooks["SessionEnd"][0]["hooks"][0]["command"] == f"{FAKE_BGM} stop"
        assert hooks["Notification"][0]["matcher"] == "permission_prompt"
        assert hooks["Notification"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play notification 0"
        # Resume hook: fires after the user answers a permission prompt;
        # bgm play work 0 is idempotent, so it only switches back to work
        # (never restarts an already playing track).
        assert hooks["PostToolUse"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"


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


def test_setup_falls_back_to_bare_bgm_when_unresolvable(fake_home: Path, patched_home):
    """which() returning None must not fail setup — bare bgm is the fallback."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
            return_value=None,
        ):
            ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
        hooks = settings["hooks"]
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm play done"


def test_setup_uses_absolute_argv0_when_which_fails(fake_home: Path, patched_home):
    """A rerun launched by absolute path must not downgrade to a bare command."""
    bgm_path = "/opt/pyenv/versions/3.12.2/bin/bgm"
    with patched_home:
        with (
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
                return_value=None,
            ),
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.sys.argv",
                [bgm_path, "setup"],
            ),
        ):
            ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == f"{bgm_path} play work 0"
    assert hooks["SessionEnd"][0]["hooks"][0]["command"] == f"{bgm_path} stop"


def test_setup_ignores_argv0_that_is_not_bgm(fake_home: Path, patched_home):
    """The local dev entry point must never be embedded as the hook command."""
    with patched_home:
        with (
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
                return_value=None,
            ),
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.sys.argv",
                ["/repo/main.py", "setup"],
            ),
        ):
            ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == "bgm stop"


def test_setup_ignores_relative_argv0(fake_home: Path, patched_home):
    """A relative argv0 would resolve against Qoder's hook cwd, so reject it."""
    with patched_home:
        with (
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
                return_value=None,
            ),
            mock.patch(
                "mythril_agent_bgm.commands.integrations.qoder.sys.argv",
                ["bin/bgm", "setup"],
            ),
        ):
            ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == "bgm stop"


def test_setup_quotes_executable_path_with_spaces(fake_home: Path, patched_home):
    """An executable path containing spaces must be quoted for the hook shell."""
    spaced = "/fake bin/bgm"
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.qoder.shutil.which",
            return_value=spaced,
        ):
            ok, _ = QoderIntegration().perform_setup()
        assert ok
        settings = json.loads((fake_home / ".qoder" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"].startswith(f"'{spaced}'")
    assert hooks["SessionEnd"][0]["hooks"][0]["command"] == f"'{spaced}' stop"


def test_legacy_bare_command_config_is_upgraded(fake_home: Path, patched_home):
    """A bare-command config is outdated; setup migrates it to absolute paths."""
    legacy_events = {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "bgm play done"}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": "bgm stop"}]}],
        "Notification": [
            {
                "matcher": "permission_prompt",
                "hooks": [{"type": "command", "command": "bgm play notification 0"}],
            }
        ],
        "PostToolUse": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
    }
    _write_settings(fake_home, legacy_events)
    settings_path = fake_home / ".qoder" / "settings.json"

    with patched_home:
        integration = QoderIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_up_to_date()

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for event in legacy_events:
        assert settings["hooks"][event][0]["hooks"][0]["command"].startswith(FAKE_BGM)


def test_registry_returns_qoder():
    integration = IntegrationRegistry.get_integration_by_id("qoder")
    assert isinstance(integration, QoderIntegration)
