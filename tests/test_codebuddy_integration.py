#!/usr/bin/env python3
"""Tests for the CodeBuddy Code AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.codebuddy import CodeBuddyIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry

#: Deterministic stand-in for the bgm executable; hook commands are built
#: from ``shutil.which("bgm")``, which would otherwise leak the developer
#: machine's real path into assertions.
FAKE_BGM = "/fake/bin/bgm"


@pytest.fixture(autouse=True)
def _patch_bgm_which():
    """Resolve bgm to a fixed absolute path for every test in this module.

    ``shutil.which`` is patched on the stdlib module itself, so this is
    process-wide, not scoped to the call site: there must be exactly one
    ``shutil.which`` call on the codebuddy setup path.
    """
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.codebuddy.shutil.which",
        return_value=FAKE_BGM,
    ):
        yield


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
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play done"
        assert hooks["SessionEnd"][0]["hooks"][0]["command"] == f"{FAKE_BGM} stop"
        assert hooks["Notification"][0]["matcher"] == "permission_prompt"
        assert hooks["Notification"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play notification 0"
        # CodeBuddy keeps its original hook set; the AskUserQuestion alert
        # is intentionally scoped to WorkBuddy.
        assert "PreToolUse" not in hooks
        # Resume hooks: fire after the user answers a permission prompt /
        # question dialog; bgm play work 0 is idempotent, so it only
        # switches back to work (never restarts an already playing track).
        for event in ("PostToolUse", "ElicitationResult", "PermissionDenied"):
            assert event in hooks
            assert hooks[event][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"


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


def test_setup_falls_back_to_bare_bgm_when_unresolvable(fake_home: Path, patched_home):
    """SC1: which() returning None must not fail setup — bare bgm is the fallback."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.codebuddy.shutil.which",
            return_value=None,
        ):
            ok, _ = CodeBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(
            (fake_home / ".codebuddy" / "settings.json").read_text(encoding="utf-8")
        )
        hooks = settings["hooks"]
        assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
        assert hooks["Stop"][0]["hooks"][0]["command"] == "bgm play done"


def test_setup_quotes_executable_path_with_spaces(fake_home: Path, patched_home):
    """An executable path containing spaces must be quoted for the hook shell."""
    spaced = "/fake bin/bgm"
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.codebuddy.shutil.which",
            return_value=spaced,
        ):
            ok, _ = CodeBuddyIntegration().perform_setup()
        assert ok
        settings = json.loads(
            (fake_home / ".codebuddy" / "settings.json").read_text(encoding="utf-8")
        )
    hooks = settings["hooks"]
    assert hooks["UserPromptSubmit"][0]["hooks"][0]["command"].startswith(f"'{spaced}'")
    assert hooks["SessionEnd"][0]["hooks"][0]["command"] == f"'{spaced}' stop"


def test_legacy_bare_command_config_is_upgraded(fake_home: Path, patched_home):
    """SC3: a bare-command config is outdated; setup migrates it to absolute paths."""
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
        "ElicitationResult": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
        "PermissionDenied": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
    }
    _write_settings(fake_home, legacy_events)
    settings_path = fake_home / ".codebuddy" / "settings.json"

    with patched_home:
        integration = CodeBuddyIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_up_to_date()

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for event in legacy_events:
        assert settings["hooks"][event][0]["hooks"][0]["command"].startswith(FAKE_BGM)


def test_registry_returns_codebuddy():
    integration = IntegrationRegistry.get_integration_by_id("codebuddy")
    assert isinstance(integration, CodeBuddyIntegration)
