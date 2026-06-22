#!/usr/bin/env python3
"""
Common functions for AI BGM.
"""

import json
import os
import shutil
import sys
from pathlib import Path

from mythril_agent_bgm.utils.platform_utils import is_windows


APP_CONFIG_DIR_NAME = "mythril-agent-bgm"
LEGACY_CONFIG_DIR_NAME = "ai-bgm"


def get_builtin_sounds_dir() -> Path:
    """
    Get the built-in sounds directory from the installed package.

    If installed via pip, use the package installation directory.
    If running directly, use the current directory.

    Returns:
        Path to the built-in sounds directory
    """
    # Try to get the package installation directory
    try:
        import importlib.resources as resources

        # For Python 3.9+
        pkg_path = resources.files("mythril_agent_bgm")
        sounds_dir = Path(str(pkg_path / "sounds"))
        if sounds_dir.exists():
            return sounds_dir
    except (ImportError, AttributeError):
        pass

    # Fallback: use the package directory from this file location
    script_dir = Path(__file__).parent.parent
    fallback_paths = [
        script_dir / "sounds",
        Path.cwd() / "mythril_agent_bgm" / "sounds",
    ]
    for sounds_dir in fallback_paths:
        if sounds_dir.exists():
            return sounds_dir

    return fallback_paths[0]


def get_builtin_assets_path() -> Path:
    """Backward-compatible alias for built-in sounds directory."""
    return get_builtin_sounds_dir()


def get_assets_path() -> Path:
    """Backward-compatible alias for built-in sounds directory."""
    return get_builtin_sounds_dir()


def _get_config_root_dir() -> Path:
    """Get the platform-specific config root directory."""
    if is_windows():
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata)
        return Path.home()
    return Path.home() / ".config"


def _get_legacy_config_dir() -> Path:
    """Get legacy config directory path used by previous versions."""
    return _get_config_root_dir() / LEGACY_CONFIG_DIR_NAME


def _merge_legacy_config_dir(primary: Path, legacy: Path) -> None:
    """Merge files from legacy config directory into the primary config directory."""
    if primary.exists() or not legacy.exists():
        return

    try:
        shutil.copytree(legacy, primary, dirs_exist_ok=True)
        print(f"Migrated legacy config directory: {legacy} -> {primary}")
    except OSError as e:
        print(f"Warning: Failed to migrate legacy config from {legacy}: {e}")


def get_config_dir() -> Path:
    """
    Get the configuration directory path (cross-platform).

    Returns:
        - Linux/macOS: ~/.config/mythril-agent-bgm
        - Windows: %APPDATA%/mythril-agent-bgm
    """
    config_dir = _get_config_root_dir() / APP_CONFIG_DIR_NAME
    legacy_config_dir = _get_legacy_config_dir()

    _merge_legacy_config_dir(config_dir, legacy_config_dir)

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_user_config_file() -> Path:
    """Get the user config.json path in the user config directory."""
    return get_config_dir() / "config.json"


def get_user_sounds_dir() -> Path:
    """Get the user sounds directory path in the user config directory."""
    return get_config_dir() / "sounds"


def _get_builtin_config_file() -> Path:
    """Get built-in config.json from package installation path."""
    try:
        import importlib.resources as resources

        pkg_path = resources.files("mythril_agent_bgm")
        config_file = Path(str(pkg_path / "config.json"))
        if config_file.exists():
            return config_file
    except (ImportError, AttributeError):
        pass

    script_dir = Path(__file__).parent.parent
    return script_dir / "config.json"


def _load_json_dict(file_path: Path) -> dict:
    """Load a JSON file and return dict content, or empty dict on invalid input."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            print(f"Warning: JSON root must be an object: {file_path}")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load JSON file {file_path}: {e}")
    return {}


def _merge_bgm_configs(base_config: dict, override_config: dict) -> dict:
    """Merge BGM config dictionaries with field-level override semantics."""
    merged: dict = dict(base_config)
    for config_name, override_value in override_config.items():
        base_value = merged.get(config_name)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            combined_value = dict(base_value)
            combined_value.update(override_value)
            merged[config_name] = combined_value
        else:
            merged[config_name] = override_value
    return merged


def get_pid_file() -> Path:
    """Get the path to the PID file."""
    return get_config_dir() / "bgm_player.pid"


def get_lock_file() -> Path:
    """Get the path to the lock file for preventing concurrent starts."""
    return get_config_dir() / "bgm_player.lock"


def get_log_file() -> Path:
    """Get the path to the log file."""
    return get_config_dir() / "bgm_player.log"


def get_selection_file() -> Path:
    """Get the path to the selection file."""
    return get_config_dir() / "selection.json"


def load_selection() -> str:
    """
    Load the selected BGM configuration from user config directory.

    Returns:
        The selected configuration name (e.g., 'default', 'maou')
    """
    config_path = get_selection_file()

    if not config_path.exists():
        # No configuration found, use default
        return "default"

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("selected", "default")


def is_bgm_enabled() -> bool:
    """
    Check if AI BGM is enabled.

    Returns:
        True if enabled (default), False if disabled
    """
    config_path = get_selection_file()

    if not config_path.exists():
        return True

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("enable", True)
    except (json.JSONDecodeError, IOError):
        return True


def set_bgm_enable(enable: bool) -> None:
    """
    Set the AI BGM enable state.

    Args:
        enable: True to enable, False to disable
    """
    config_path = get_selection_file()

    # Load existing config or create new one
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Update enable state
    data["enable"] = enable

    # Save config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_builtin_config() -> dict:
    """
    Load merged BGM config.

    Merge order:
    1. Built-in package config: mythril_agent_bgm/config.json
    2. User config (optional): <config_dir>/config.json

    For same top-level config names, user fields override built-in fields.

    Returns:
        Dictionary containing all BGM configurations
    """
    config_file = _get_builtin_config_file()

    if not config_file.exists():
        print(f"Error: Config file not found at {config_file}")
        sys.exit(1)

    config = _load_json_dict(config_file)

    user_config_file = get_user_config_file()
    if user_config_file.exists():
        user_config = _load_json_dict(user_config_file)
        if user_config:
            config = _merge_bgm_configs(config, user_config)

    return config


def get_audio_candidate_paths(selection: str, file_name: str) -> list[Path]:
    """Build candidate paths for an audio file in user and built-in directories.

    Audio files are stored directly in the sounds/ directory (no subdirectories).
    User sounds override built-in sounds when filenames match.
    """
    builtin_sounds = get_builtin_sounds_dir()
    user_sounds = get_user_sounds_dir()

    # Only use the bare filename; subdirectories are not supported
    bare_name = Path(file_name).name

    return [user_sounds / bare_name, builtin_sounds / bare_name]


def resolve_audio_file_path(selection: str, file_name: str) -> Path | None:
    """Resolve an audio file path by checking user sounds first, then built-in sounds."""
    for candidate in get_audio_candidate_paths(selection, file_name):
        if candidate.exists():
            return candidate
    return None


def save_pid() -> None:
    """Save the current process PID to the PID file."""
    pid_file = get_pid_file()
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))


_USER_CONFIG_README_TEMPLATE = r"""# mythril-agent-bgm User Configuration

This directory is for your personal BGM customizations.
Files here are NOT affected by pip install/upgrade/uninstall.

## Quick Start

1. Add your `.mp3` files directly into `sounds/` (no subdirectories)
2. Edit `config.json` and reference files by bare filename
3. Run `bgm select` to choose your configuration
4. Run `bgm play work 0` to start

## Config Example

```json
{{
  "my_collection": {{
    "work": ["my_song.mp3", "another_song.mp3"],
    "done": ["done.mp3"]
  }}
}}
```

- `work` — music played during work (looped)
- `done` — music played when work finishes
- `notification` — notification sounds

## File Rules

- All `.mp3` files go directly in `sounds/` — **no subdirectories**
- If your file has the same name as a built-in file, yours takes priority

## How Merge Works

- Built-in config: package `mythril_agent_bgm/config.json`
- Your config: `{config_dir}/config.json`
- Same config key: your fields override built-in fields
- Audio files: user `sounds/` checked first, then built-in sounds

## Uninstall

```bash
rm -rf {config_dir}
```
"""


def _get_user_config_readme_content() -> str:
    """Generate user config README content with platform-specific paths."""
    config_dir = str(get_config_dir())
    return _USER_CONFIG_README_TEMPLATE.format(config_dir=config_dir)


def ensure_user_config_dir() -> None:
    """
    Ensure the user config directory is initialized.

    Creates the directory, a starter config.json, a sounds/ subdirectory,
    and a README.md on first run. Safe to call multiple times.
    """
    config_dir = get_config_dir()
    user_config_file = get_user_config_file()
    user_sounds_dir = get_user_sounds_dir()
    readme_file = config_dir / "README.md"

    if not user_config_file.exists():
        starter_config = {
            "my_collection": {
                "work": [
                    "default_boss.mp3",
                    "default_castle.mp3",
                    "default_desert.mp3",
                    "default_forest.mp3",
                    "default_battle_a.mp3",
                    "default_battle_b.mp3",
                    "default_battle_c.mp3",
                    "default_lastboss_a.mp3",
                    "default_lastboss_b.mp3",
                    "default_medley.mp3",
                    "default_mountain.mp3",
                    "default_pause.mp3",
                    "default_snow.mp3",
                    "default_village.mp3",
                ],
                "done": ["default_congratulations.mp3"],
                "notification": ["default_pause.mp3"],
            }
        }
        user_config_file.write_text(
            json.dumps(starter_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[mythril-agent-bgm] Created starter config: {user_config_file}")

    if not user_sounds_dir.exists():
        user_sounds_dir.mkdir(parents=True, exist_ok=True)
        print(f"[mythril-agent-bgm] Created sounds directory: {user_sounds_dir}")

    if not readme_file.exists():
        readme_file.write_text(_get_user_config_readme_content(), encoding="utf-8")
        print(f"[mythril-agent-bgm] Created README: {readme_file}")


def cleanup_pid() -> None:
    """Remove the PID file."""
    pid_file = get_pid_file()
    if pid_file.exists():
        pid_file.unlink()
