#!/usr/bin/env python3
"""
Gemini CLI integration for AI BGM.
"""

from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


class GeminiIntegration(AIToolIntegration):
    """Integration for Gemini CLI."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get Gemini CLI tool information."""
        return ("gemini", "Gemini CLI")

    def get_settings_path(self) -> Path:
        """Get Gemini CLI settings path."""
        return Path.home() / ".gemini" / "settings.json"

    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup Gemini CLI hooks.

        Configures hooks for:
        - BeforeAgent: User submits prompt -> start work music
        - AfterAgent: Agent response ends -> play done music
        - SessionEnd: Session ends -> stop all music
        - Notification: Play notification music

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary
        """
        # Enable hooks in tools
        if "tools" not in settings:
            settings["tools"] = {}
        settings["tools"]["enableHooks"] = True

        # Enable hooks config
        if "hooksConfig" not in settings:
            settings["hooksConfig"] = {}
        settings["hooksConfig"]["enabled"] = True

        # Initialize hooks if it doesn't exist
        if "hooks" not in settings:
            settings["hooks"] = {}

        # Configure hooks for AI BGM
        settings["hooks"]["BeforeAgent"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "name": "Play work music",
                        "type": "command",
                        "command": "bgm play work 0",
                        "description": "Play work music",
                    }
                ],
            }
        ]
        settings["hooks"]["AfterAgent"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "name": "Play done music",
                        "type": "command",
                        "command": "bgm play done",
                        "description": "Play done music",
                    }
                ],
            }
        ]
        settings["hooks"]["SessionEnd"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "name": "Stop music",
                        "type": "command",
                        "command": "bgm stop",
                        "description": "Stop all music",
                    }
                ],
            }
        ]
        settings["hooks"]["Notification"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "name": "Play notification music",
                        "type": "command",
                        "command": "bgm play notification 0",
                        "description": "Play notification music",
                    }
                ],
            }
        ]

        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        """Remove BGM hooks and related config from Gemini CLI settings."""
        hooks = settings.get("hooks", {})
        for key in ("BeforeAgent", "AfterAgent", "SessionEnd", "Notification"):
            hooks.pop(key, None)
        if not hooks:
            settings.pop("hooks", None)

        tools = settings.get("tools", {})
        tools.pop("enableHooks", None)
        if not tools:
            settings.pop("tools", None)

        hooks_config = settings.get("hooksConfig", {})
        hooks_config.pop("enabled", None)
        if not hooks_config:
            settings.pop("hooksConfig", None)

        return settings
