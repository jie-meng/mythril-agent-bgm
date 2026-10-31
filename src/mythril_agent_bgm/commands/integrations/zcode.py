#!/usr/bin/env python3
"""
ZCode integration for AI BGM.

ZCode stores hooks in ``~/.zcode/cli/config.json`` under a top-level
``hooks`` object shaped as::

    { "enabled": true, "events": { "<Event>": [ { "matcher": "...", "hooks": [...] } ] } }

Configuration-file hooks only run when ``hooks.enabled`` is true, so setup
sets it. ZCode supports exactly seven events (``SessionStart``,
``UserPromptSubmit``, ``PreToolUse``, ``PermissionRequest``, ``PostToolUse``,
``PostToolUseFailure``, ``Stop``) - there is no ``SessionEnd`` and no
``Notification``.

Hook commands are written with the absolute path of the ``bgm`` executable
(resolved via ``shutil.which``, then ``sys.argv[0]``, at setup time; the bare
name is kept only when neither yields a usable absolute path). ZCode 3.17.1
runs hooks with a sanitized PATH (homebrew + system + its bundled tools) that
has no pyenv shims, so a bare ``bgm`` fails with exit 127 (command not found)
and no music plays.

Reference: the ``zcode-configuration-guide`` and ``diagnosing-hooks`` skills
shipped with the ZCode client.
"""

import shlex
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


def _bgm_path() -> str:
    """Resolve the executable embedded in ZCode hook commands.

    ``which`` is the normal case, but only an absolute result is usable: a
    relative PATH entry would bake a cwd-relative command into the hook.
    When setup was itself launched by absolute path under a sanitized PATH
    (``/abs/bin/bgm setup``), ``sys.argv[0]`` still carries that absolute
    path, so a rerun never downgrades an existing absolute hook back to a
    bare command. ``argv[0]`` is only trusted when it is absolute and looks
    like bgm, so a non-bgm entry point (e.g. the local ``main.py``) is never
    embedded.
    """
    which_path = shutil.which("bgm")
    if which_path and Path(which_path).is_absolute():
        return which_path

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and Path(argv0).is_absolute() and Path(argv0).stem.lower().startswith("bgm"):
        return argv0

    return "bgm"


def _bgm_command(*args: str) -> str:
    """Build a bgm hook command using the absolute executable path."""
    return " ".join([shlex.quote(_bgm_path()), *args])


class ZcodeIntegration(AIToolIntegration):
    """Integration for ZCode."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get ZCode tool information."""
        return ("zcode", "ZCode")

    def get_settings_path(self) -> Path:
        """Get ZCode settings path."""
        return Path.home() / ".zcode" / "cli" / "config.json"

    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup ZCode hooks.

        Configures hooks for:
        - UserPromptSubmit: Start work music
        - Stop: Play done music
        - PermissionRequest: Play notification music
        - PostToolUse: Switch back to work music once the user answers a
          permission prompt. ``bgm play work 0`` is idempotent (a no-op while
          work music is already playing), so hooking it on a frequent event
          never restarts the current track.

        ZCode has no session-end event, so playback is not stopped when the
        session closes.

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary
        """
        hooks = settings.setdefault("hooks", {})
        # Configuration-file hooks are skipped unless explicitly enabled.
        hooks["enabled"] = True
        events = hooks.setdefault("events", {})
        events.update(self._bgm_events())
        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        """Remove BGM hooks from ZCode settings."""
        hooks = settings.get("hooks", {})
        events = hooks.get("events", {})
        for event in self._bgm_events():
            events.pop(event, None)
        if not events:
            hooks.pop("events", None)
            hooks.pop("enabled", None)
        if not hooks:
            settings.pop("hooks", None)
        return settings

    @staticmethod
    def _bgm_events() -> Dict[str, List[dict]]:
        """Build the BGM hook matchers keyed by ZCode event name."""

        def entry(command: str) -> List[dict]:
            return [{"hooks": [{"type": "command", "command": command}]}]

        return {
            "UserPromptSubmit": entry(_bgm_command("play", "work", "0")),
            "Stop": entry(_bgm_command("play", "done")),
            "PermissionRequest": entry(_bgm_command("play", "notification", "0")),
            "PostToolUse": entry(_bgm_command("play", "work", "0")),
        }
