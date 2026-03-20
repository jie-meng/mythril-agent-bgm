# AI Tool Integrations

This directory contains integration modules for various AI CLI tools.

## Structure

- `__init__.py` - Base `AIToolIntegration` abstract class
- `registry.py` - Integration registry that manages all integrations
- `claude.py` - Claude Code integration
- `cursor_agent.py` - Cursor Agent integration
- `gemini.py` - Gemini CLI integration
- `opencode.py` - OpenCode integration (plugin-based)

## Adding a New Integration

### Step 1: Create Integration File

Create a new file `<toolname>.py`:

```python
#!/usr/bin/env python3
"""
New Tool integration for AI BGM.
"""

from pathlib import Path
from typing import Tuple

from mythril_agent_bgm.commands.integrations import AIToolIntegration


class NewToolIntegration(AIToolIntegration):
    """Integration for New Tool."""

    def get_tool_info(self) -> Tuple[str, str]:
        """Get tool information."""
        return ("newtool", "New Tool Name")

    def get_settings_path(self) -> Path:
        """Get settings path."""
        return Path.home() / ".newtool" / "settings.json"

    def setup_hooks(self, settings: dict) -> dict:
        """Setup hooks for New Tool."""
        hooks_config = {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "bgm play work 0"}]}
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "bgm play done"}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": "bgm stop"}]}],
        }

        if "hooks" not in settings:
            settings["hooks"] = {}

        settings["hooks"]["UserPromptSubmit"] = hooks_config["UserPromptSubmit"]
        settings["hooks"]["Stop"] = hooks_config["Stop"]
        settings["hooks"]["SessionEnd"] = hooks_config["SessionEnd"]

        return settings
```

### Step 2: Register Integration

Add your integration to `registry.py`:

```python
from mythril_agent_bgm.commands.integrations.newtool import NewToolIntegration

class IntegrationRegistry:
    _integrations: List[Type[AIToolIntegration]] = [
        ClaudeIntegration,
        NewToolIntegration,  # Add here
    ]
```

### Step 3: Test

```bash
bgm setup
# Your new tool should appear in the menu
```

## Design Principles

1. **Isolation**: Each integration is self-contained in its own file
2. **Interface**: All integrations implement the same `AIToolIntegration` interface
3. **Registry**: Central registry automatically discovers all integrations
4. **Extensibility**: Easy to add new integrations without modifying existing code

## Available Integrations

- **Claude Code**: [Hooks Documentation](https://code.claude.com/docs/en/hooks)
- **Cursor Agent**: [Hooks Documentation](https://cursor.com/cn/docs/agent/hooks)
- **Gemini CLI**: [Hooks Documentation](https://geminicli.com/docs/hooks/)
- **OpenCode**: [Plugins Documentation](https://opencode.ai/docs/plugins/) — uses a JS plugin file instead of JSON hooks
