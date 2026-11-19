#!/usr/bin/env python3
"""
Claude Code integration for AI BGM.
"""

import shlex
import shutil
import sys
from pathlib import Path
from typing import Dict, Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


def _bgm_path() -> str:
    """Resolve the executable embedded in Claude Code hook commands.

    ``which`` is the normal case. When setup was itself launched by absolute
    path under a sanitized PATH (``/abs/bin/bgm setup``), ``sys.argv[0]``
    still carries that absolute path, so a rerun never downgrades an
    existing absolute hook back to a bare command. ``argv[0]`` is only
    trusted when it is absolute and looks like bgm: a relative path would
    resolve against Claude Code's hook cwd, and a wrapper entry point is
    never embedded.
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


def _is_bgm_handler(handler: object) -> bool:
    """Check whether a hook handler was installed by bgm.

    The first token is normalised across platforms: backslashes to slashes,
    last path segment, lowercase, trailing ``.exe`` removed. Only the quoted
    form this integration writes is handled -- an unquoted Windows path is
    not re-parsed.
    """
    if not isinstance(handler, dict):
        return False

    command = handler.get("command")
    if not isinstance(command, str) or not command:
        return False

    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    if not tokens:
        return False

    name = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    return name == "bgm"


def _strip_bgm_handlers(groups: object) -> Tuple[list, bool]:
    """Remove bgm handlers from one event's hook groups.

    Malformed groups are kept as-is so a hand-edited settings file is never
    rewritten beyond the handlers this integration owns.
    """
    if not isinstance(groups, list):
        return ([], False)

    kept: list = []
    changed = False
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            kept.append(group)
            continue

        handlers = group["hooks"]
        remaining = [handler for handler in handlers if not _is_bgm_handler(handler)]
        if len(remaining) == len(handlers):
            kept.append(group)
            continue

        changed = True
        if remaining:
            updated = dict(group)
            updated["hooks"] = remaining
            kept.append(updated)

    return (kept, changed)


class ClaudeIntegration(AIToolIntegration):
    """Integration for Claude Code."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get Claude Code tool information."""
        return ("claude", "Claude Code")

    def get_settings_path(self) -> Path:
        """Get Claude Code settings path."""
        return Path.home() / ".claude" / "settings.json"

    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup Claude Code hooks.

        Configures hooks for:
        - UserPromptSubmit: Start work music
        - Stop: Keep work music while background tasks run, otherwise play done
        - SessionEnd: Stop all music
        - Notification(permission_prompt): Play notification music
        - Notification(idle_prompt): Replace running work music with done
        - PostToolUse / PostToolUseFailure: Resume work music after the user
          answers a permission prompt. ``bgm resume`` only acts while
          notification music is still playing, so tool calls that run after
          the turn ended (background agents, workflows) cannot restart work.

        Handlers installed by other tools are preserved; only bgm's own
        handlers are replaced.

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary
        """
        hooks_config: Dict[str, list] = {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": _bgm_command("play", "work", "0")}]}
            ],
            "Stop": [{"hooks": [{"type": "command", "command": _bgm_command("hook", "stop")}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": _bgm_command("stop")}]}],
            "Notification": [
                {
                    "matcher": "permission_prompt",
                    "hooks": [
                        {"type": "command", "command": _bgm_command("play", "notification", "0")}
                    ],
                },
                {
                    "matcher": "idle_prompt",
                    "hooks": [{"type": "command", "command": _bgm_command("hook", "idle")}],
                },
            ],
            "PostToolUse": [{"hooks": [{"type": "command", "command": _bgm_command("resume")}]}],
            "PostToolUseFailure": [
                {"hooks": [{"type": "command", "command": _bgm_command("resume")}]}
            ],
        }

        # Initialize hooks if it doesn't exist
        if "hooks" not in settings:
            settings["hooks"] = {}

        # Replace only bgm's own handlers, keeping other tools' groups in place
        for event, groups in hooks_config.items():
            kept, _ = _strip_bgm_handlers(settings["hooks"].get(event))
            settings["hooks"][event] = kept + groups

        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        """Remove BGM hooks from Claude Code settings."""
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            return settings

        for event in (
            "UserPromptSubmit",
            "Stop",
            "SessionEnd",
            "Notification",
            "PostToolUse",
            "PostToolUseFailure",
        ):
            if event not in hooks:
                continue

            kept, changed = _strip_bgm_handlers(hooks[event])
            if not changed:
                continue

            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event)

        if not hooks:
            settings.pop("hooks", None)

        return settings
