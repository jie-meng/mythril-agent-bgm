#!/usr/bin/env python3
"""Tests for the ZCode AI tool integration."""

import json
from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry
from mythril_agent_bgm.commands.integrations.zcode import ZcodeIntegration

#: Deterministic stand-in for the bgm executable; hook commands are built
#: from ``shutil.which("bgm")``, which would otherwise leak the developer
#: machine's real path into assertions.
FAKE_BGM = "/fake/bin/bgm"


@pytest.fixture(autouse=True)
def _patch_bgm_which():
    """Resolve bgm to a fixed absolute path for every test in this module."""
    with mock.patch(
        "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
        return_value=FAKE_BGM,
    ):
        yield


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .zcode/cli config root."""
    zcode_dir = tmp_path / ".zcode" / "cli"
    zcode_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.zcode.Path.home",
        return_value=fake_home,
    )


def _settings_path(fake_home: Path) -> Path:
    return fake_home / ".zcode" / "cli" / "config.json"


def _write_config(fake_home: Path, hooks: dict) -> None:
    _settings_path(fake_home).write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def _read_config(fake_home: Path) -> dict:
    return json.loads(_settings_path(fake_home).read_text(encoding="utf-8"))


def test_tool_info():
    assert ZcodeIntegration().get_tool_info() == ("zcode", "ZCode")


def test_settings_path_under_zcode_cli(patched_home):
    with patched_home:
        assert ZcodeIntegration().get_settings_path() == (
            Path.home() / ".zcode" / "cli" / "config.json"
        )


def test_config_dir_is_zcode_cli(patched_home):
    with patched_home:
        assert ZcodeIntegration().get_config_dir() == Path.home() / ".zcode" / "cli"


def test_setup_adds_all_hooks(fake_home: Path, patched_home):
    with patched_home:
        ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        hooks = _read_config(fake_home)["hooks"]

    # Configuration-file hooks are skipped by ZCode unless enabled.
    assert hooks["enabled"] is True
    events = hooks["events"]
    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"
    assert events["Stop"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play done"
    assert (
        events["PermissionRequest"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play notification 0"
    )
    assert events["PostToolUse"][0]["hooks"][0]["command"] == f"{FAKE_BGM} play work 0"


def test_setup_keeps_other_settings_and_events(fake_home: Path, patched_home):
    _write_config(
        fake_home,
        {
            "enabled": True,
            "events": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]},
        },
    )
    path = _settings_path(fake_home)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["mcp"] = {"servers": {}}
    path.write_text(json.dumps(raw), encoding="utf-8")

    with patched_home:
        ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        settings = _read_config(fake_home)

    assert settings["mcp"] == {"servers": {}}
    events = settings["hooks"]["events"]
    assert events["SessionStart"] == [{"hooks": [{"type": "command", "command": "x"}]}]
    assert "PostToolUse" in events


def test_setup_enables_hooks_when_disabled(fake_home: Path, patched_home):
    _write_config(fake_home, {"enabled": False, "events": {}})

    with patched_home:
        ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        assert _read_config(fake_home)["hooks"]["enabled"] is True


def test_setup_cleanup_roundtrip(fake_home: Path, patched_home):
    with patched_home:
        integration = ZcodeIntegration()
        assert not integration.is_configured()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_configured()
        assert integration.is_up_to_date()

        ok, _ = integration.perform_cleanup()
        assert ok
        assert not integration.is_configured()
        assert "hooks" not in _read_config(fake_home)


def test_cleanup_removes_only_bgm_hooks(fake_home: Path, patched_home):
    _write_config(
        fake_home,
        {
            "enabled": True,
            "events": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]},
        },
    )

    with patched_home:
        ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        ok, _ = ZcodeIntegration().perform_cleanup()
        assert ok
        settings = _read_config(fake_home)

    assert "PostToolUse" not in settings["hooks"]["events"]
    assert settings["hooks"]["events"]["SessionStart"] == [
        {"hooks": [{"type": "command", "command": "x"}]}
    ]


def test_up_to_date_detects_missing_resume_hook(fake_home: Path, patched_home):
    # Simulate a pre-resume config: the three lifecycle hooks but no PostToolUse.
    # Commands already use the absolute path, so the missing event is the only
    # difference from the desired state.
    _write_config(
        fake_home,
        {
            "enabled": True,
            "events": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": f"{FAKE_BGM} play work 0"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": f"{FAKE_BGM} play done"}]}],
                "PermissionRequest": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"{FAKE_BGM} play notification 0",
                            }
                        ]
                    }
                ],
            },
        },
    )
    with patched_home:
        integration = ZcodeIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()


def test_setup_falls_back_to_bare_bgm_when_unresolvable(fake_home: Path, patched_home):
    """which() returning None must not fail setup — bare bgm is the fallback."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
            return_value=None,
        ):
            with mock.patch(
                "mythril_agent_bgm.commands.integrations.zcode.sys.argv",
                ["/usr/bin/python3", "setup"],
            ):
                ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        events = _read_config(fake_home)["hooks"]["events"]

    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"
    assert events["Stop"][0]["hooks"][0]["command"] == "bgm play done"


def test_setup_uses_absolute_argv0_when_which_fails(fake_home: Path, patched_home):
    """A rerun launched by absolute path must not downgrade to a bare command."""
    bgm_path = "/opt/pyenv/versions/3.12.2/bin/bgm"
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
            return_value=None,
        ):
            with mock.patch(
                "mythril_agent_bgm.commands.integrations.zcode.sys.argv",
                [bgm_path, "setup"],
            ):
                ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        events = _read_config(fake_home)["hooks"]["events"]

    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == f"{bgm_path} play work 0"
    assert events["Stop"][0]["hooks"][0]["command"] == f"{bgm_path} play done"


def test_setup_ignores_relative_which_path(fake_home: Path, patched_home):
    """A relative PATH entry must not bake a cwd-relative command into the hook."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
            return_value="bin/bgm",
        ):
            with mock.patch(
                "mythril_agent_bgm.commands.integrations.zcode.sys.argv",
                ["/usr/bin/python3", "setup"],
            ):
                ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        events = _read_config(fake_home)["hooks"]["events"]

    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"


def test_setup_ignores_relative_argv0(fake_home: Path, patched_home):
    """A relative argv0 would resolve against ZCode's hook cwd, so reject it."""
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
            return_value=None,
        ):
            with mock.patch(
                "mythril_agent_bgm.commands.integrations.zcode.sys.argv",
                ["bin/bgm", "setup"],
            ):
                ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        events = _read_config(fake_home)["hooks"]["events"]

    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == "bgm play work 0"


def test_setup_quotes_executable_path_with_spaces(fake_home: Path, patched_home):
    """An executable path containing spaces must be quoted for the hook shell."""
    spaced = "/fake bin/bgm"
    with patched_home:
        with mock.patch(
            "mythril_agent_bgm.commands.integrations.zcode.shutil.which",
            return_value=spaced,
        ):
            ok, _ = ZcodeIntegration().perform_setup()
        assert ok
        events = _read_config(fake_home)["hooks"]["events"]

    assert events["UserPromptSubmit"][0]["hooks"][0]["command"] == f"'{spaced}' play work 0"
    assert events["Stop"][0]["hooks"][0]["command"] == f"'{spaced}' play done"


def test_legacy_bare_command_config_is_upgraded(fake_home: Path, patched_home):
    """A bare-command config is outdated; setup migrates it to absolute paths."""
    _write_config(
        fake_home,
        {
            "enabled": True,
            "events": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": "bgm play work 0"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": "bgm play done"}]}],
                "PermissionRequest": [
                    {"hooks": [{"type": "command", "command": "bgm play notification 0"}]}
                ],
                "PostToolUse": [{"hooks": [{"type": "command", "command": "bgm play work 0"}]}],
            },
        },
    )
    with patched_home:
        integration = ZcodeIntegration()
        assert integration.is_configured()
        assert not integration.is_up_to_date()

        ok, _ = integration.perform_setup()
        assert ok
        assert integration.is_up_to_date()
        events = _read_config(fake_home)["hooks"]["events"]

    for event in ("UserPromptSubmit", "Stop", "PermissionRequest", "PostToolUse"):
        assert events[event][0]["hooks"][0]["command"].startswith(FAKE_BGM)


def test_registry_returns_zcode():
    integration = IntegrationRegistry.get_integration_by_id("zcode")
    assert isinstance(integration, ZcodeIntegration)
