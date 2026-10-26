#!/usr/bin/env python3
"""
Qoder integration for AI BGM.

Qoder uses the same declarative ``hooks`` format as Claude Code:
a ``hooks`` object keyed by event name -> array of matcher objects ->
array of command objects, stored in ``~/.qoder/settings.json``
(user-wide) or ``<project>/.qoder/settings.json`` (project-local).

Hook commands are written with the absolute path of the ``bgm`` executable
(resolved via ``shutil.which``, then ``sys.argv[0]``, at setup time). Qoder
0.4.11 runs hooks through a non-login ``/bin/bash`` whose PATH has no pyenv
shims, so a bare ``bgm`` fails with exit 127 (command not found) and no
music plays.

Reference: https://docs.qoder.com/extensions/hooks
"""

import shlex
import shutil
import sys
from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


def _bgm_path() -> str:
    """Resolve the executable embedded in Qoder hook commands.

    ``which`` is the normal case. When setup was itself launched by absolute
    path under a sanitized PATH (``/abs/bin/bgm setup``), ``sys.argv[0]``
    still carries that absolute path, so a rerun never downgrades an
    existing absolute hook back to a bare command. ``argv[0]`` is only
    trusted when it is absolute and looks like bgm: a relative path would
    resolve against Qoder's hook cwd, and a wrapper entry point is never
    embedded.
    """
    which_path = shutil.which("bgm")
    if which_path:
        return which_path

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and Path(argv0).is_absolute() and Path(argv0).stem.lower().startswith("bgm"):
        return argv0

    return "bgm"


def _bgm_command(*args: str) -> str:
    """Build a bgm hook command using the absolute executable path."""
    return " ".join([shlex.quote(_bgm_path()), *args])


class QoderIntegration(AIToolIntegration):
    """Integration for Qoder."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get Qoder tool information."""
        return ("qoder", "Qoder")

    def get_settings_path(self) -> Path:
        """Get Qoder settings path."""
        return Path.home() / ".qoder" / "settings.json"

    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup Qoder hooks.

        Configures hooks for:
        - UserPromptSubmit: Start work music
        - Stop: Play done music
        - SessionEnd: Stop all music
        - Notification: Play notification music (only on permission_prompt)
        - PostToolUse: Switch back to work music after the user answers a
          permission prompt. ``bgm play work 0`` is idempotent (a no-op while
          work music is already playing), so hooking it on a frequent event
          like PostToolUse never restarts the current track.

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary
        """
        hooks_config = {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": _bgm_command("play", "work", "0")}]}
            ],
            "Stop": [{"hooks": [{"type": "command", "command": _bgm_command("play", "done")}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": _bgm_command("stop")}]}],
            "Notification": [
                {
                    "matcher": "permission_prompt",
                    "hooks": [
                        {"type": "command", "command": _bgm_command("play", "notification", "0")}
                    ],
                }
            ],
            "PostToolUse": [
                {"hooks": [{"type": "command", "command": _bgm_command("play", "work", "0")}]}
            ],
        }

        # Initialize hooks if it doesn't exist
        if "hooks" not in settings:
            settings["hooks"] = {}

        # Update hooks, keep other hooks intact
        for key, value in hooks_config.items():
            settings["hooks"][key] = value

        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        """Remove BGM hooks from Qoder settings."""
        hooks = settings.get("hooks", {})
        for key in ("UserPromptSubmit", "Stop", "SessionEnd", "Notification", "PostToolUse"):
            hooks.pop(key, None)
        if not hooks:
            settings.pop("hooks", None)
        return settings
