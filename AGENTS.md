# AGENTS.md

AI agent guidelines for working on the AI BGM project.

## System Context

**Project Type**: CLI tool for AI-assisted work sessions
**Language**: Python 3.9+
**Audio**: pygame.mixer
**Package**: pyproject.toml

## Key Facts for AI Agents

### What This Project Does

- Plays background music during AI-assisted work
- Auto-stops when AI finishes (via hooks)
- Supports multiple BGM configurations
- Runs as daemon process

### Important Conventions

- Use **Black** (line length 100) for formatting
- Type hints required for function signatures
- Use `pathlib.Path`, not `os.path`
- Config paths (cross-platform):
  - Linux/macOS: `~/.config/bgm/`
  - Windows: `%APPDATA%\bgm\`
- User selection in `selection.json` within config directory

### Design Principles

Follow these core principles when writing code:

#### 1. Single Responsibility Principle (SRP)
Each module/class should have one reason to change. Platform logic is isolated in `platform_utils.py` and `process.py`.

#### 2. Separation of Concerns (SoC)
Keep platform-specific code out of business logic. Use `ProcessManager`, `FileLock`, and platform helpers instead.

#### 3. Don't Repeat Yourself (DRY)
Don't check `platform.system()` multiple times. Use the provided helpers: `is_windows()`, `is_unix()`.

#### 4. Open/Closed Principle
Code should be open for extension, closed for modification. Add new platform support by extending utilities, not by adding conditionals everywhere.

#### 5. Cross-Platform Implementation
- Always use `aibgm.utils.platform_utils` for platform detection
- Always use `aibgm.utils.process` for process management
- Never write `if platform.system() == "Windows"` in business code
- See [docs/Refactoring.md](docs/Refactoring.md) for detailed examples

### Critical Paths

| Path | Purpose |
|------|---------|
| `aibgm/config.json` | BGM configurations |
| `aibgm/cli.py` | Unified CLI entry point |
| `main.py` | Local development entry (not packaged) |
| `aibgm/utils/platform_utils.py` | Platform detection utilities |
| `aibgm/utils/process.py` | Cross-platform process management |

### Daemon Behavior

- PID file: `bgm_player.pid` in config directory
- Log file: `bgm_player.log` in config directory
  - Auto-rotates at 1000 lines
  - Keeps last 500 lines
- Kill with `SIGTERM`, fallback `SIGKILL`
- File locks used on Unix (fcntl), Windows uses PID file only

## Common Tasks

### Platform-Specific Code

Use utilities from `aibgm.utils.platform_utils` and `aibgm.utils.process`:
- **Platform detection**: `is_windows()`, `is_unix()`
- **Process management**: `ProcessManager.kill_process()`, `ProcessManager.check_process_exists()`
- **File locking**: `FileLock` context manager
- **Signal handlers**: `setup_signal_handlers()`

See source files for detailed usage (docstrings and type hints).

### Add Music Config

```bash
# 1. Add files to aibgm/assets/sounds/<name>/
# 2. Update aibgm/config.json
{
  "<name>": {
    "work": ["file.mp3"],
    "done": ["done.mp3"]
  }
}
# 3. Test: bgm select
```

### Add CLI Option

In `cli.py`, use Click decorators:
```python
@cli.command()
@click.option("--option", is_flag=True)
def my_command(option):
    # Use: option
    pass
```

### Add AI Tool

Adding a new AI tool integration:

1. Create `aibgm/commands/integrations/<toolname>.py`
2. Implement `AIToolIntegration` abstract class (including `cleanup_hooks`)
3. Register in `aibgm/commands/integrations/registry.py`

Example:
```python
from aibgm.commands.integrations import AIToolIntegration

class NewToolIntegration(AIToolIntegration):
    def get_tool_info(self) -> Tuple[str, str]:
        return ("newtool", "New Tool Name")
    
    def get_settings_path(self) -> Path:
        return Path.home() / ".newtool" / "settings.json"
    
    def setup_hooks(self, settings: dict) -> dict:
        # Configure hooks
        return settings

    def cleanup_hooks(self, settings: dict) -> dict:
        # Remove hooks
        return settings
```

Then register:
```python
# In registry.py
_integrations = [
    ClaudeIntegration,
    IFlowIntegration,
    NewToolIntegration,  # Add here
]
```

## Testing

### Unit Tests
```bash
# Run cross-platform compatibility tests
python tests/test_windows_compat.py
```

### Code Quality
```bash
# Format
black aibgm/

# Lint
flake8 aibgm/

# Type check
mypy aibgm/
```

### Manual Testing
```bash
# Test basic functionality
bgm play work 0
bgm stop
bgm select

# Test setup / cleanup cycle
bgm setup
bgm cleanup
```

### When Adding New Features

1. **Run existing tests first** to ensure baseline works
2. **Add tests** for new functionality in `tests/`
3. **Test on current platform** (macOS/Linux/Windows)
4. **Verify cross-platform** if touching platform-specific code

## Constraints

- Don't modify `docs/Dev.md` (user maintains)
- Don't add new dependencies without approval
- Keep changes minimal and focused
- Test before committing

## Getting Help

- User guide: [README.md](README.md)
- Dev setup: [docs/Dev.md](docs/Dev.md)
