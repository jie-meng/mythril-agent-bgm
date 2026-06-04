#!/usr/bin/env python3
"""
Base class for AI tool integrations.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple


class AIToolIntegration(ABC):
    """
    Abstract base class for AI tool integrations.

    Each integration must implement:
    - get_tool_info(): Return (tool_id, tool_name)
    - get_settings_path(): Return path to settings file
    - setup_hooks(settings): Configure hooks in settings
    - cleanup_hooks(settings): Remove hooks from settings

    Subclasses may override:
    - get_config_dir(): Return the tool's config root directory for install detection
    - perform_setup(): Customize the full setup flow (default: JSON read/write)
    - perform_cleanup(): Customize the full cleanup flow (default: JSON read/write)
    - is_configured(): Customize how to detect existing BGM configuration
    """

    @abstractmethod
    def get_tool_info(self) -> Tuple[str, str]:
        """
        Get tool information.

        Returns:
            Tuple of (tool_id, tool_name)
        """
        pass

    @abstractmethod
    def get_settings_path(self) -> Path:
        """
        Get the path to the tool's settings file.

        Returns:
            Path to settings.json
        """
        pass

    @abstractmethod
    def setup_hooks(self, settings: dict) -> dict:
        """
        Setup hooks in the settings dictionary.

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary
        """
        pass

    @abstractmethod
    def cleanup_hooks(self, settings: dict) -> dict:
        """
        Remove BGM hooks from the settings dictionary.

        Args:
            settings: Existing settings dictionary

        Returns:
            Updated settings dictionary with BGM hooks removed
        """
        pass

    def get_config_dir(self) -> Path:
        """
        Get the tool's config root directory for install detection.

        Defaults to the parent of get_settings_path().
        Override when the settings file is nested deeper than the config root.
        """
        return self.get_settings_path().parent

    def perform_setup(self) -> Tuple[bool, str]:
        """
        Execute the full setup flow.

        Default implementation: load JSON settings, apply hooks, save.
        Subclasses can override for non-JSON setup (e.g. writing a plugin file).
        """
        settings_path = self.get_settings_path()
        tool_id, tool_name = self.get_tool_info()

        config_dir = self.get_config_dir()
        if not config_dir.exists():
            return (False, f"{tool_name}: Config directory not found ({config_dir})")

        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {}

        settings = self.setup_hooks(settings)

        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        return (True, f"{tool_name}: Configured successfully [OK]")

    def perform_cleanup(self) -> Tuple[bool, str]:
        """
        Execute the full cleanup flow.

        Default implementation: load JSON settings, remove hooks, save.
        Subclasses can override for non-JSON cleanup (e.g. deleting a plugin file).
        """
        settings_path = self.get_settings_path()
        tool_id, tool_name = self.get_tool_info()

        if not settings_path.exists():
            return (True, f"{tool_name}: No settings file found, nothing to clean up")

        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        settings = self.cleanup_hooks(settings)

        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        return (True, f"{tool_name}: Cleaned up successfully [OK]")

    def validate_settings_path(self) -> bool:
        """
        Check if settings file exists.

        Returns:
            True if settings file exists, False otherwise
        """
        return self.get_settings_path().exists()

    def is_configured(self) -> bool:
        """
        Check whether BGM hooks/plugins are currently installed for this tool.

        Default implementation: for JSON-based integrations, load the settings
        file and detect whether cleanup_hooks() would change anything. If
        cleanup leaves the dict unchanged, there are no BGM hooks to remove,
        so the tool is not configured.

        Subclasses with file-based integrations (e.g. a standalone plugin file)
        should override this with a direct file-existence check.

        Returns:
            True if BGM is already set up for this tool, False otherwise.
        """
        settings_path = self.get_settings_path()
        if not settings_path.exists():
            return False

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        before = json.dumps(settings, sort_keys=True)
        after_settings = self.cleanup_hooks(json.loads(before))
        after = json.dumps(after_settings, sort_keys=True)
        return before != after

    def is_up_to_date(self) -> bool:
        """
        Check whether the current settings already match what setup_hooks() would write.

        Default implementation: for JSON-based integrations, apply setup_hooks() to a
        copy of the current settings and compare. Returns True only when setup_hooks()
        would produce no change — meaning the on-disk config is already the desired state.

        Because setup_hooks() only modifies BGM-managed keys and leaves all other
        settings (permissions, env, user-defined hooks, etc.) untouched, this comparison
        is sensitive only to BGM-related keys. User changes to unrelated settings will
        never trigger a false "outdated" result.

        Subclasses with file-based integrations (e.g. OpenCode, Copilot) must override
        this to compare file content against the expected generated output.

        Returns:
            True if the integration is configured and fully up to date, False otherwise.
        """
        settings_path = self.get_settings_path()
        if not settings_path.exists():
            return False

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        before = json.dumps(settings, sort_keys=True)
        after_settings = self.setup_hooks(json.loads(before))
        after = json.dumps(after_settings, sort_keys=True)
        return before == after
