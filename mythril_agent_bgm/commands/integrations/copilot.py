#!/usr/bin/env python3
"""
GitHub Copilot CLI integration for AI BGM.

Copilot CLI loads user-level hooks from any ``*.json`` file under
``~/.copilot/hooks/`` (or ``$COPILOT_HOME/hooks/`` if set). Multiple files
are merged, so we install a dedicated ``mythril-agent-bgm.json`` rather
than touching the user's ``settings.json``. This keeps setup/cleanup
trivial: drop a file in / remove a file out.

References:
- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks
- https://docs.github.com/en/copilot/reference/hooks-reference
"""

import json
import os
from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration

HOOK_FILE_NAME = "mythril-agent-bgm.json"


def _copilot_home() -> Path:
    """Resolve Copilot's config root, honoring the ``COPILOT_HOME`` override."""
    override = os.environ.get("COPILOT_HOME")
    if override:
        return Path(override)
    return Path.home() / ".copilot"


class CopilotIntegration(AIToolIntegration):
    """Integration for GitHub Copilot CLI via a dedicated user-level hooks file."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get GitHub Copilot CLI tool information."""
        return ("copilot", "GitHub Copilot CLI")

    def get_settings_path(self) -> Path:
        """Path to the BGM-managed hooks file inside Copilot's hooks directory."""
        return _copilot_home() / "hooks" / HOOK_FILE_NAME

    def get_config_dir(self) -> Path:
        """Copilot config root used to detect whether the CLI is installed."""
        return _copilot_home()

    def setup_hooks(self, settings: dict) -> dict:
        """Not used (file-based setup). Returns settings unchanged."""
        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        """Not used (file-based cleanup). Returns settings unchanged."""
        return settings

    def is_configured(self) -> bool:
        """BGM is configured iff the managed hooks file exists."""
        return self.get_settings_path().exists()

    def perform_setup(self) -> Tuple[bool, str]:
        """Write the BGM hooks JSON into Copilot's user-level hooks directory."""
        config_dir = self.get_config_dir()
        if not config_dir.exists():
            return (False, f"GitHub Copilot CLI: Config directory not found ({config_dir})")

        hooks_path = self.get_settings_path()
        hooks_path.parent.mkdir(parents=True, exist_ok=True)

        with open(hooks_path, "w", encoding="utf-8") as f:
            json.dump(self._build_hooks_payload(), f, indent=2, ensure_ascii=False)

        return (True, "GitHub Copilot CLI: Configured successfully [OK]")

    def perform_cleanup(self) -> Tuple[bool, str]:
        """Remove the BGM hooks JSON file from Copilot's hooks directory."""
        hooks_path = self.get_settings_path()
        if not hooks_path.exists():
            return (True, "GitHub Copilot CLI: No hooks file found, nothing to clean up")

        hooks_path.unlink()
        return (True, "GitHub Copilot CLI: Cleaned up successfully [OK]")

    @staticmethod
    def _build_hooks_payload() -> dict:
        """Build the hook configuration mapped to BGM lifecycle commands.

        Event mapping (Copilot CLI -> BGM):
        - userPromptSubmitted -> start work music
        - agentStop           -> play done music
        - sessionEnd          -> stop all music
        - notification        -> play notification music

        ``bash`` and ``powershell`` both invoke ``bgm`` directly so the same
        configuration works on macOS, Linux, and Windows.
        """

        def entry(cmd: str) -> dict:
            return {
                "type": "command",
                "bash": cmd,
                "powershell": cmd,
                "timeoutSec": 5,
            }

        return {
            "version": 1,
            "hooks": {
                "userPromptSubmitted": [entry("bgm play work 0")],
                "agentStop": [entry("bgm play done")],
                "sessionEnd": [entry("bgm stop")],
                "notification": [entry("bgm play notification 0")],
            },
        }
