#!/usr/bin/env python3
"""
CodeBuddy Code integration for AI BGM.

CodeBuddy Code uses the same declarative ``hooks`` format as Claude Code:
a ``hooks`` object keyed by event name -> array of matcher objects ->
array of command objects, stored in ``~/.codebuddy/settings.json``
(user-wide) or ``<project>/.codebuddy/settings.json`` (project-local).

Hook commands are written with the absolute path of the ``bgm`` executable
(resolved via ``shutil.which`` at setup time). Host apps may run hooks with
a sanitized PATH — the WorkBuddy desktop engine, for one, starts its CLI
with a PATH lacking pyenv/homebrew shims, so a bare ``bgm`` would fail with
exit 127 (command not found). The absolute path works in both environments.

Reference: https://www.codebuddy.ai/docs/cli/hooks-guide
"""

import shlex
import shutil
from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


def _bgm_command(*args: str) -> str:
    """Build a bgm hook command using the absolute executable path.

    Resolves ``bgm`` via ``shutil.which`` at call time and quotes it, so the
    command runs under the host's sanitized hook PATH (WorkBuddy desktop)
    as well as a normal terminal PATH. Falls back to the bare ``bgm`` when
    it cannot be resolved — never fails setup over PATH resolution, and no
    worse than the previous bare-command behavior.
    """
    bgm = shutil.which("bgm") or "bgm"
    return " ".join([shlex.quote(bgm), *args])


class CodeBuddyIntegration(AIToolIntegration):
    """Integration for CodeBuddy Code."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get CodeBuddy Code tool information."""
        return ("codebuddy", "CodeBuddy Code")

    def get_settings_path(self) -> Path:
        """Get CodeBuddy Code settings path."""
        return Path.home() / ".codebuddy" / "settings.json"

    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup CodeBuddy Code hooks.

        Configures hooks for:
        - UserPromptSubmit: Start work music
        - Stop: Play done music
        - SessionEnd: Stop all music
        - Notification: Play notification music (only on permission_prompt, not idle_prompt)
        - PostToolUse/ElicitationResult/PermissionDenied: Switch back to work
          music. These fire after the user answers a permission prompt or
          question dialog. ``bgm play work 0`` is idempotent (a no-op while
          work music is already playing), so hooking it on frequent events
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
            "ElicitationResult": [
                {"hooks": [{"type": "command", "command": _bgm_command("play", "work", "0")}]}
            ],
            "PermissionDenied": [
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
        """Remove BGM hooks from CodeBuddy Code settings."""
        hooks = settings.get("hooks", {})
        for key in (
            "UserPromptSubmit",
            "Stop",
            "SessionEnd",
            "Notification",
            "PostToolUse",
            "ElicitationResult",
            "PermissionDenied",
        ):
            hooks.pop(key, None)
        if not hooks:
            settings.pop("hooks", None)
        return settings
