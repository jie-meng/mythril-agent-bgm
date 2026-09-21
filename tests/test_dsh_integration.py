#!/usr/bin/env python3
"""Tests for the DeepSeek Harness (dsh) AI tool integration."""

from pathlib import Path
from unittest import mock

import pytest

from mythril_agent_bgm.commands.integrations.dsh import DshIntegration
from mythril_agent_bgm.commands.integrations.registry import IntegrationRegistry


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake home directory with a .dsh web profile."""
    profile = tmp_path / ".dsh" / "profiles" / "web"
    profile.mkdir(parents=True)
    return tmp_path


def _make_bgm(home: Path) -> Path:
    """Create a fake bgm executable inside the fake home."""
    fake_bgm = home / "fake-bgm"
    fake_bgm.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    fake_bgm.chmod(0o755)
    return fake_bgm


@pytest.fixture
def patched_home(fake_home: Path):
    return mock.patch(
        "mythril_agent_bgm.commands.integrations.dsh.Path.home",
        return_value=fake_home,
    )


def test_tool_info():
    assert DshIntegration().get_tool_info() == ("dsh", "DeepSeek Harness")


def test_settings_path_under_dsh_profile(patched_home):
    with patched_home:
        assert DshIntegration().get_settings_path() == (
            Path.home()
            / ".dsh"
            / "profiles"
            / "web"
            / "node_modules"
            / "mythril-agent-bgm-dsh"
            / "index.js"
        )


def test_generate_plugin_contains_expected_pieces():
    plugin = DshIntegration._generate_plugin("/x/bgm")
    assert "play work 0" in plugin
    assert "play done" in plugin
    # The user's answer to a question arrives as tool/result, not
    # user/message: its callId must resume work music (notification does not
    # loop until the next prompt).
    assert "pendingQuestions" in plugin
    assert "event.data?.message?.source?.callId" in plugin
    assert "play notification 0" in plugin
    assert "stop" in plugin
    assert "ask_user_question" in plugin
    assert "agent/status" in plugin
    assert "session/event" in plugin
    assert "session/disposed" in plugin
    assert '"user/message"' in plugin
    assert "isRootSession" in plugin
    assert "DEBOUNCE_MS" in plugin
    # Cordis requires services used inside session/event callbacks to be
    # declared via inject (session-scoped dispatch cannot resolve ctx.agents
    # from the fiber chain; without this the user/message branch throws
    # "cannot get property 'agents' without inject").
    assert 'export const inject = ["agents"];' in plugin
    assert '"/x/bgm"' in plugin
    # ask_user_question resets the work debounce so the user's immediate
    # reply restarts work music (the reset also appears in session/disposed;
    # the assertion guards that the template contains the reset at all).
    assert "lastWorkTime = 0" in plugin
    # The done cue is gated on work music having actually played.
    assert "runningRoots.size === 0 && lastWorkTime > 0" in plugin


def test_generate_plugin_work_triggered_by_user_message_not_agent_status():
    # Regression guard: work music must start on a real user prompt
    # (user/message in a root session), NOT on session/agent startup
    # (agent/status running fires when dsh web resumes a session without
    # any user input). The single `play work 0` call must live inside the
    # session/event handler, after the user/message check.
    plugin = DshIntegration._generate_plugin("/x/bgm")
    assert plugin.index('"agent/status"') < plugin.index('"user/message"')
    assert plugin.index('"user/message"') < plugin.index('run("play", "work", "0")')
    # agent/status handler only does bookkeeping + the done cue, never work.
    status_block = plugin[plugin.index('"agent/status"') : plugin.index('"session/event"')]
    assert 'run("play", "work", "0")' not in status_block
    # Direct guard (upgrades the position inference above to a guard
    # condition assertion): the work trigger is debounced on lastWorkTime,
    # and the ask_user_question branch resets it so the user's immediate
    # reply restarts work music.
    assert "isRootSession(session) && now - lastWorkTime > DEBOUNCE_MS" in plugin


def test_generate_plugin_swallows_spawn_errors():
    # Regression guard: async spawn 'error' events must never crash dsh.
    plugin = DshIntegration._generate_plugin("/x/bgm")
    assert '.on("error"' in plugin
    assert "windowsHide" in plugin
    assert "child.unref()" in plugin


def test_generate_plugin_embeds_windows_bgm_path():
    # JSON-escaped backslashes must stay valid inside the generated JS.
    plugin = DshIntegration._generate_plugin(r"C:\tools\bgm.exe")
    assert r'"C:\\tools\\bgm.exe"' in plugin


def test_up_to_date_false_after_patch_entry_removed(fake_home: Path, patched_home):
    fake_bgm = _make_bgm(fake_home)
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            ok, _ = integration.perform_setup()
            assert ok
            assert integration.is_up_to_date()
            # Remove only the patch entry (what cleanup does to the patch),
            # leaving the plugin package intact.
            assert integration._remove_patch_entry()
            assert not integration.is_up_to_date()


def test_strip_patch_entry_preserves_prefix_id_block(fake_home: Path, patched_home):
    # A `- id: mythril-agent-bgm-legacy` block must not be matched by the
    # exact-id check; cleanup removes only the real BGM block.
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    legacy = "- insert:\n" "    - id: mythril-agent-bgm-legacy\n" "      name: some-legacy-pkg\n"
    entry = "- insert:\n    - id: mythril-agent-bgm\n      name: mythril-agent-bgm-dsh\n"
    tail = "- id: other-row\n  disabled: false\n"
    patch.write_text(legacy + entry + "\n" + tail, encoding="utf-8")
    with patched_home:
        ok, _ = DshIntegration().perform_cleanup()
        assert ok
    assert patch.read_text(encoding="utf-8") == legacy + tail


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_strip_patch_entry_middle_block_preserves_tail_blank_lines(eol: str):
    # A BGM block in the MIDDLE of the content, followed by a tail that
    # itself ends in multiple blank lines: stripping must keep those
    # trailing blank lines byte-for-byte (regression: unconditional tail
    # normalization used to fold them into a single line ending). Tested
    # directly on the pure function because Path.read_text universal-newline
    # handling would normalize CRLF away before _strip_patch_entry sees it.
    head = "# comment" + eol
    entry = (
        "- insert:"
        + eol
        + "    - id: mythril-agent-bgm"
        + eol
        + "      name: mythril-agent-bgm-dsh"
        + eol
    )
    tail = "- id: other-row" + eol + "  disabled: false" + eol + eol + eol
    stripped = DshIntegration._strip_patch_entry(head + entry + eol + tail)
    assert stripped == head + tail


def test_patch_read_failure_falls_back(fake_home: Path, patched_home):
    # Unreadable cordis.patch.yml must degrade to False / a failure message
    # instead of raising through the curses UI (mock keeps this Windows-safe).
    fake_bgm = _make_bgm(fake_home)
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    patch.write_text("", encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            with mock.patch.object(Path, "read_text", side_effect=OSError("permission denied")):
                assert not integration.is_configured()
                assert not integration.is_up_to_date()
                ok, message = integration.perform_setup()
                assert not ok
                assert "Unable to read" in message


def test_setup_package_write_failure_falls_back(fake_home: Path, patched_home):
    # An unwritable profile node_modules (e.g. read-only) must degrade to a
    # failure message instead of raising through the curses UI. Mocked to
    # stay cross-platform (Windows chmod-based read-only is unreliable).
    fake_bgm = _make_bgm(fake_home)
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            with mock.patch.object(Path, "write_text", side_effect=OSError("permission denied")):
                ok, message = integration.perform_setup()
                assert not ok
                assert "Unable to write plugin package" in message


def test_patch_append_preserves_other_entries(fake_home: Path, patched_home):
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    other = "# comment\n- id: session-title-llm\n  disabled: true\n"
    patch.write_text(other, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            ok, _ = DshIntegration().perform_setup()
            assert ok
    assert patch.read_text(encoding="utf-8") == (
        other + "- insert:\n    - id: mythril-agent-bgm\n      name: mythril-agent-bgm-dsh\n"
    )


def test_patch_remove_preserves_other_entries(fake_home: Path, patched_home):
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    head = "# comment\n- id: session-title-llm\n  disabled: true\n"
    entry = "- insert:\n    - id: mythril-agent-bgm\n      name: mythril-agent-bgm-dsh\n"
    tail = "- id: other-row\n  disabled: false\n"
    patch.write_text(head + entry + "\n" + tail, encoding="utf-8")
    with patched_home:
        ok, _ = DshIntegration().perform_cleanup()
        assert ok
    assert patch.read_text(encoding="utf-8") == head + tail


def test_setup_cleanup_idempotent(fake_home: Path, patched_home):
    fake_bgm = _make_bgm(fake_home)
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            ok, _ = integration.perform_setup()
            assert ok
            first = patch.read_text(encoding="utf-8")
            assert first.count("- insert:") == 1

            ok, _ = integration.perform_setup()
            assert ok
            assert patch.read_text(encoding="utf-8") == first

            ok, _ = integration.perform_cleanup()
            assert ok
            assert not patch.exists()
            ok, message = integration.perform_cleanup()
            assert ok
            assert "nothing to clean up" in message


def test_setup_cleanup_roundtrip(fake_home: Path, patched_home):
    fake_bgm = _make_bgm(fake_home)
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            assert not integration.is_configured()

            ok, _ = integration.perform_setup()
            assert ok
            assert integration.is_configured()
            assert integration.is_up_to_date()
            package_dir = integration.get_settings_path().parent
            assert (package_dir / "index.js").exists()
            assert (package_dir / "package.json").exists()

            ok, _ = integration.perform_cleanup()
            assert ok
            assert not integration.is_configured()
            assert not package_dir.exists()


def test_outdated_when_index_js_modified(fake_home: Path, patched_home):
    fake_bgm = _make_bgm(fake_home)
    with patched_home:
        with mock.patch("shutil.which", return_value=str(fake_bgm)):
            integration = DshIntegration()
            ok, _ = integration.perform_setup()
            assert ok
            assert integration.is_up_to_date()

            index = integration.get_settings_path()
            index.write_text(
                index.read_text(encoding="utf-8") + "\n// tampered\n", encoding="utf-8"
            )
            assert not integration.is_up_to_date()


# dsh's profile scaffold writes cordis.patch.yml with this exact content:
# three comment lines plus a bare `[]` empty-array placeholder.
_DSH_SCAFFOLD_PATCH = (
    "# Your patch layer for this dsh profile, applied after every bundle layer:\n"
    "# a top-level YAML array of loader patch entries (id-targeted config\n"
    "# overrides, disables, and insert lists; `!!js` expressions allowed).\n"
    "[]\n"
)
_ENTRY = "- insert:\n    - id: mythril-agent-bgm\n      name: mythril-agent-bgm-dsh\n"


def test_setup_replaces_dsh_empty_array_placeholder(fake_home: Path, patched_home):
    # Regression: dsh scaffolds cordis.patch.yml with a bare `[]`; appending
    # the entry after it yields invalid YAML, and dsh fails loud on an
    # unparsable patch layer ("end of the stream or a document separator is
    # expected"). The placeholder must be dropped, not appended after.
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    patch.write_text(_DSH_SCAFFOLD_PATCH, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            assert DshIntegration().perform_setup()[0]
    result = patch.read_text(encoding="utf-8")
    assert "[]" not in result
    assert result == _DSH_SCAFFOLD_PATCH.replace("[]\n", "") + _ENTRY


def test_setup_repairs_patch_broken_by_placeholder(fake_home: Path, patched_home):
    # An already-installed entry sitting below the placeholder: setup is
    # idempotent for the entry, but must still strip the placeholder so an
    # existing broken install is repaired on the next `bgm setup`.
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    patch.write_text(_DSH_SCAFFOLD_PATCH + _ENTRY, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            integration = DshIntegration()
            assert integration.perform_setup()[0]
            assert integration.is_up_to_date()
    assert patch.read_text(encoding="utf-8") == _DSH_SCAFFOLD_PATCH.replace("[]\n", "") + _ENTRY


def test_append_preserves_nested_empty_arrays(fake_home: Path, patched_home):
    # Only the top-level `[]` placeholder goes; indented empty arrays (a
    # nested `config: []`) belong to other entries and must survive.
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    other = "- id: session-title-llm\n  config: []\n"
    patch.write_text(other, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            assert DshIntegration().perform_setup()[0]
    assert patch.read_text(encoding="utf-8") == other + _ENTRY


def test_cleanup_restores_empty_array_placeholder(fake_home: Path, patched_home):
    # After cleanup the file holds comments only, which parses as `null` and
    # would trip "must be a top-level YAML array": the `[]` placeholder has
    # to come back (unless nothing at all is left, in which case the file is
    # deleted and dsh treats it as "no user layer").
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    patch.write_text(_DSH_SCAFFOLD_PATCH.replace("[]\n", "") + _ENTRY, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            assert DshIntegration().perform_cleanup()[0]
    assert patch.read_text(encoding="utf-8") == _DSH_SCAFFOLD_PATCH


def test_setup_cleanup_roundtrip_over_dsh_scaffold(fake_home: Path, patched_home):
    # Full roundtrip on a scaffolded profile: the file is left byte-identical
    # to what dsh generated, so dsh still parses it after cleanup.
    patch = fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
    patch.write_text(_DSH_SCAFFOLD_PATCH, encoding="utf-8")
    with patched_home:
        with mock.patch("shutil.which", return_value=str(_make_bgm(fake_home))):
            integration = DshIntegration()
            assert integration.perform_setup()[0]
            assert integration.perform_cleanup()[0]
    assert patch.read_text(encoding="utf-8") == _DSH_SCAFFOLD_PATCH


def test_setup_requires_profile_dir(tmp_path: Path):
    # No .dsh web profile dir -> setup reports failure without creating files.
    with mock.patch("mythril_agent_bgm.commands.integrations.dsh.Path.home", return_value=tmp_path):
        ok, message = DshIntegration().perform_setup()
        assert not ok
        assert "Profile directory not found" in message


def test_setup_requires_bgm(fake_home: Path, patched_home):
    with patched_home:
        with mock.patch("shutil.which", return_value=None):
            ok, message = DshIntegration().perform_setup()
            assert not ok
            assert "'bgm' command not found" in message


def test_registry_returns_dsh():
    integration = IntegrationRegistry.get_integration_by_id("dsh")
    assert isinstance(integration, DshIntegration)
