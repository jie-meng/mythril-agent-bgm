# mythril-agent-bgm

mythril-agent-bgm - A cross-platform tool that plays work music during work sessions and integrates with AI tools.

## Quick Start

```bash
# 1. Install
pip install .

# 2. Setup AI tool integration (e.g., Claude Code)
bgm setup

# 3. Select your BGM configuration
bgm select

# 4. Done! Music will auto-play when AI is working
```

## Installation

### Prerequisites

- Python 3.9+
- pip

### Install

```bash
pip install .
```

If you encounter externally-managed-environment error, then you can install by

```bash
pip install . --break-system-packages
```

This installs CLI command:
- `bgm` - Unified CLI with subcommands: play, stop, select, setup, cleanup

### System Dependencies

**macOS**: None required.

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev libsdl2-dev

# Fedora
sudo dnf install python3-devel SDL2-devel
```

**Windows**: None required.

## Usage

### First Time Setup

#### 1. Select BGM Configuration

```bash
bgm select
```

Interactively choose from available configurations (e.g., `default`). Selection is saved to:
- **Linux/macOS**: `~/.config/bgm/selection.json`
- **Windows**: `%APPDATA%\bgm\selection.json`

#### 2. Setup AI Tool Integration

```bash
bgm setup
```

Currently supports:

- **Claude Code**
- **Cursor** (Cursor Hooks Notification not yet supported)
- **Gemini CLI**
- **iFlow CLI**
- **OpenCode**

#### 3. Cleanup AI Tool Integration (reverse of setup)

```bash
bgm cleanup
```

Removes BGM hooks/plugins from AI tools. Interactively select which tools to clean up.

### Manual Commands

#### Play Work Music

```bash
bgm play work 0     # Loop indefinitely
bgm play work 3     # Play 3 times
bgm play done       # Play done music once
```

#### Stop Music

```bash
bgm stop
```

Stops any playing music.

### Test BGM

```bash
# Test play (single done music)
bgm play done

# Test work music loop (Ctrl+C to stop)
bgm play work 0

# Verify configuration
bgm select
```

### Editor Integration

#### Neovim

Add to your `init.lua`:

```lua
keymap.set("n", "<F10>", function()
  vim.fn.jobstart("bgm toggle")
end, { desc = "Toggle AI BGM" })
```

Press `F10` to toggle BGM playback/pause.

#### Vim

Add to your `.vimrc`:

```vim
nnoremap <F10> :call system('bgm toggle')<CR>
```

Press `F10` to toggle BGM playback/pause.

## Custom Configuration

### Add Custom Music

#### Method 1: Using config_ext.json (Recommended for copyrighted music)

For copyrighted music that should NOT be committed to the repository:

1. **Create a music directory** in `aibgm/assets/sounds/<your-config>/`

```bash
mkdir -p aibgm/assets/sounds/my_collection
cp /path/to/your/song.mp3 aibgm/assets/sounds/my_collection/
```

2. **Create or edit `aibgm/config_ext.json`** (this file is ignored by git):

```json
{
  "my_collection": {
    "work": ["song1.mp3", "song2.mp3"],
    "done": ["complete.mp3"]
  }
}
```

3. **Select your config**:

```bash
bgm-select
```

**How it works**:
- `config.json` contains built-in configurations (default, maou)
- `config_ext.json` contains your custom configurations
- If a key exists in both files, `config_ext.json` takes precedence
- `config_ext.json` is gitignored, so your copyrighted music won't be uploaded

#### Method 2: Using config.json (For royalty-free music only)

For royalty-free music that can be shared:

1. **Place audio files** in `aibgm/assets/sounds/<your-config>/`

```bash
mkdir -p aibgm/assets/sounds/my_music
cp /path/to/your/song.mp3 aibgm/assets/sounds/my_music/
```

2. **Update config.json**:

```json
{
  "my_music": {
    "work": ["song1.mp3", "song2.mp3"],
    "done": ["complete.mp3"]
  }
}
```

3. **Select your config**:

```bash
bgm select
```

### Music Licensing

**IMPORTANT**: Only music that is free for commercial use or royalty-free should be committed to this repository.

**Included Configurations**:

- **default**: Music from [Maou Audio](https://maou.audio/)
  - License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
  - Free for personal and commercial use
  - Modification and redistribution allowed with attribution
  - **DO NOT**: Use for AI music training, claim as your own, or sell on streaming platforms
  - Attribution: "Music: Maou Audio"

**⚠️ Copyright Warning**:

- Do NOT commit copyrighted music files to this repository
- Only add music that you have explicit permission to use and distribute
- **For copyrighted music**: Use `config_ext.json` and custom directories in `assets/sounds/`
  - These are automatically gitignored and won't be uploaded
  - Perfect for personal music collections
  - Example: Create `assets/sounds/my_collection/` and configure it in `config_ext.json`
- **For royalty-free music**: Add to `config.json` and appropriate directories
- The `.gitignore` file is configured to ignore all directories except `default`

3. **Select your config**:

```bash
bgm select
```

### Config Structure

| Field | Description |
|-------|-------------|
| `work` | List of music files to play during work |
| `done` | List of music files to play when done |
| `notification` | List of music files for notifications |

**File Path Formats**:

- **Simple name**: `song.mp3` → Reads from `assets/sounds/<config-name>/song.mp3`
- **With folder**: `default/song.mp3` → Reads from `assets/sounds/default/song.mp3`

**Example**:

```json
{
  "my_config": {
    "work": [
      "my_song.mp3",
      "default/boss.mp3"
    ],
    "done": [
      "default/congratulations.mp3"
    ]
  }
}
```

## File Structure

```
bgm/
├── aibgm/
│   ├── cli.py             # Unified CLI entry point
│   ├── config.json        # Built-in music configurations
│   ├── config_ext.json    # Custom music configurations (gitignored)
│   └── assets/sounds/     # Audio files
│       └── default/
├── main.py                # Local development entry point
├── docs/
│   └── Dev.md             # Development guide
├── pyproject.toml
└── README.md
```

## Troubleshooting

**No sound?**
```bash
# Check pygame
pip show pygame

# Check log (Linux/macOS)
cat ~/.config/bgm/bgm_player.log
tail -50 ~/.config/bgm/bgm_player.log  # Last 50 lines

# Windows
type %APPDATA%\bgm\bgm_player.log
```

**Music won't stop?**
```bash
# Force kill if needed (Linux/macOS)
ps aux | grep bgm
kill <pid>
rm ~/.config/bgm/bgm_player.pid

# Windows
tasklist | findstr bgm
taskkill /PID <pid> /F
del %APPDATA%\bgm\bgm_player.pid
```

**Log file management**

The daemon log file is automatically managed:
- **Linux/macOS**: `~/.config/bgm/bgm_player.log`
- **Windows**: `%APPDATA%\bgm\bgm_player.log`
- Maximum 1000 lines before rotation
- Keeps most recent 500 lines after rotation
- No manual cleanup needed

## License

MIT

## Development

See [docs/Dev.md](docs/Dev.md) for development guide.
