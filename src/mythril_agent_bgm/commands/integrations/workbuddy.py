#!/usr/bin/env python3
"""
WorkBuddy AI integration for AI BGM.

WorkBuddy AI (the Tencent desktop AI workbench) is built on the CodeBuddy
engine, so it consumes the exact same declarative ``hooks`` format as
CodeBuddy Code and Claude Code: a ``hooks`` object keyed by event name ->
array of matcher objects -> array of command objects.

Only the config directory differs. The desktop app injects
``WORKBUDDY_CONFIG_DIR`` / ``CODEBUDDY_CONFIG_DIR`` into the engine it
spawns, so its settings file resolves to ``<config-dir>/settings.json``:

* overseas edition (``workbuddy-ai`` product) -> ``~/.workbuddy-ai/settings.json``
* other editions                              -> ``~/.workbuddy/settings.json``

Because the hook schema is identical, this integration reuses the hook set
from :class:`CodeBuddyIntegration` and only overrides the tool identity and
the config location. If the two ever need to diverge, break the inheritance
and copy the hook map.

Reference: https://www.codebuddy.ai/docs/cli/hooks
"""

import os
from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations.codebuddy import CodeBuddyIntegration

#: Config directories to probe, in priority order. ``.workbuddy-ai`` is the
#: overseas WorkBuddy AI data dir; ``.workbuddy`` is the fallback used by the
#: other editions.
CANDIDATE_CONFIG_DIRS = (".workbuddy-ai", ".workbuddy")

#: Env var the WorkBuddy desktop app injects into the engine it spawns.
CONFIG_DIR_ENV = "WORKBUDDY_CONFIG_DIR"


class WorkBuddyIntegration(CodeBuddyIntegration):
    """Integration for WorkBuddy AI."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get WorkBuddy AI tool information."""
        return ("workbuddy", "WorkBuddy AI")

    def get_config_dir(self) -> Path:
        """Resolve the WorkBuddy AI config directory.

        Resolution order:

        1. ``WORKBUDDY_CONFIG_DIR`` — set when bgm runs as a WorkBuddy child
           process (and lets tests point at a fixture directory).
        2. The first existing candidate under the user home, so both the
           ``.workbuddy-ai`` and ``.workbuddy`` editions are detected.
        3. ``~/.workbuddy-ai`` — the overseas default, used when nothing
           exists yet.
        """
        from_env = os.environ.get(CONFIG_DIR_ENV, "").strip()
        if from_env:
            return Path(from_env).expanduser()

        home = Path.home()
        for name in CANDIDATE_CONFIG_DIRS:
            candidate = home / name
            if candidate.is_dir():
                return candidate

        return home / CANDIDATE_CONFIG_DIRS[0]

    def get_settings_path(self) -> Path:
        """Get the WorkBuddy AI settings path (``<config-dir>/settings.json``)."""
        return self.get_config_dir() / "settings.json"
