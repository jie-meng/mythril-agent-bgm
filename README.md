# mythril-agent-bgm

English | [中文](./README.zh-CN.md)

> "AI fatigue is real." - [Siddhant Khare](https://siddhantkhare.com/writing/ai-fatigue-is-real)

`mythril-agent-bgm` is a cross-platform CLI tool that adds audio feedback to AI-assisted coding sessions.
It plays looped work music while the agent is active, plays a done cue when work finishes, and stops
automatically at session end.

## Why

AI coding sessions are productive but mentally expensive.
This tool helps by turning invisible state changes into simple audio cues:

- `work` music loops when the agent is actively working
- `done` cue plays when a task finishes
- playback stops automatically when the session ends

This reduces constant status-checking and makes long sessions less draining.

## Install

```bash
pip install mythril-agent-bgm

# Upgrade
pip install -U mythril-agent-bgm
```

This installs the `bgm` command.

## Quick Start

On first run, any `bgm` command initializes your user config directory with starter files.

1. `bgm setup` - install hooks/plugins for detected AI tools
2. `bgm select` - choose a BGM profile (`default` or your custom profile)
3. `bgm enable` - enable automatic BGM behavior

Optional quick check:

```bash
bgm play work 0
bgm stop
```

## Supported Integrations

- Claude Code
- Cursor Agent
- Gemini CLI
- OpenCode (plugin-based)

`bgm setup` only configures tools detected on your machine.

## Config Paths

- macOS/Linux: `~/.config/mythril-agent-bgm/`
- Windows: `%APPDATA%\mythril-agent-bgm\`

Important files:

- `config.json` - custom BGM profiles
- `selection.json` - selected profile and enable/disable state
- `sounds/` - user `.mp3` files (flat directory, no subdirectories)
- `bgm_player.pid` - daemon process ID
- `bgm_player.log` - daemon log file

## Customize Audio

1. Copy `.mp3` files into your user `sounds/` directory.
2. Edit your user `config.json`:

```json
{
  "my_collection": {
    "work": ["my_song.mp3", "another.mp3"],
    "done": ["done.mp3"],
    "notification": ["ping.mp3"]
  }
}
```

3. Run `bgm select` and choose `my_collection`.

Notes:

- profile names are arbitrary (`my_collection` is only an example)
- user audio files override built-in files when names are the same
- only bare filenames are supported (no nested paths)

## Common Commands

```bash
bgm play work 0          # Loop work music indefinitely
bgm play work 3          # Play work music 3 times
bgm play done            # Play done music once
bgm play notification    # Play notification sound
bgm stop                 # Stop current playback daemon
bgm toggle               # Toggle play/stop
bgm select               # Choose profile
bgm setup                # Configure integrations
bgm cleanup              # Remove integration changes
bgm enable               # Enable automatic BGM
bgm disable              # Disable automatic BGM
```

## Troubleshooting

```bash
# Verify pygame is installed
pip show pygame

# Stop active playback
bgm stop
```

If issues continue, inspect files in your config directory:

- `bgm_player.log`
- `bgm_player.pid`

## Uninstall

```bash
pip uninstall mythril-agent-bgm
```

Optional: remove your user config directory manually.

## Development

See [docs/Dev.md](docs/Dev.md).
