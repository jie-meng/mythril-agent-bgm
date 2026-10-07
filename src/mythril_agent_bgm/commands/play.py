#!/usr/bin/env python3
"""
Play music command for AI BGM.
"""

import os
import shutil
import sys
import time
import subprocess
import random
from pathlib import Path
from typing import Optional

import click
import pygame

from mythril_agent_bgm.utils.common import (
    get_pid_file,
    get_lock_file,
    load_selection,
    load_builtin_config,
    save_pid,
    cleanup_pid,
    save_state,
    clear_state,
    load_state,
    is_bgm_enabled,
    get_audio_candidate_paths,
    resolve_audio_file_path,
)
from mythril_agent_bgm.utils.logger import LogManager
from mythril_agent_bgm.utils.process import ProcessManager, FileLock, setup_signal_handlers
from mythril_agent_bgm.utils.platform_utils import is_windows


def kill_existing_process() -> Optional[int]:
    """
    Kill any existing BGM player process.

    Returns:
        The PID of the killed process, or None if there was none.
    """
    pid_file = get_pid_file()

    if not pid_file.exists():
        return None

    try:
        with open(pid_file, "r") as f:
            old_pid = int(f.read().strip())

        # Check if the process is still running
        if not ProcessManager.check_process_exists(old_pid):
            # Process doesn't exist, remove stale PID file
            pid_file.unlink()
            return None

        # Kill the existing process
        killed = ProcessManager.kill_process(old_pid, graceful=True, timeout=2.0)

        # Clean up PID file if it still exists
        if pid_file.exists():
            pid_file.unlink()

        return old_pid if killed else None
    except (ValueError, IOError):
        return None


def play_music(selection: str, music_type: str, repeat: int = 1) -> None:
    """
    Play music based on selection and type.

    Args:
        selection: The selected configuration name (e.g., 'default', 'maou')
        music_type: Either 'work', 'done', or 'notification'
        repeat: Number of times to play. 0 for infinite loop, 1+ for specified count.
    """
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: repeat parameter = {repeat}, type = {type(repeat)}"
    )
    sys.stdout.flush()
    config = load_builtin_config()

    if selection not in config:
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: Configuration '{selection}' not found in config.json",
            err=True,
        )
        cleanup_pid()
        sys.exit(1)

    if music_type not in config[selection]:
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: Music type '{music_type}' not found in configuration '{selection}'",
            err=True,
        )
        cleanup_pid()
        sys.exit(1)

    files = config[selection][music_type]

    if not files:
        # No files configured, do nothing
        cleanup_pid()
        return

    # Randomly select one file
    selected_file = random.choice(files)

    full_path = resolve_audio_file_path(selection, selected_file)

    if full_path is None:
        checked_paths = get_audio_candidate_paths(selection, selected_file)
        checked_paths_str = ", ".join(str(path) for path in checked_paths)
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: File not found: {selected_file}",
            err=True,
        )
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checked paths: {checked_paths_str}",
            err=True,
        )
        cleanup_pid()
        sys.exit(1)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Playing: {selected_file}")
    sys.stdout.flush()

    # Initialize pygame mixer
    try:
        pygame.mixer.init()
    except pygame.error as e:
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error initializing audio: {e}",
            err=True,
        )
        cleanup_pid()
        sys.exit(1)

    try:
        # Load the music file
        pygame.mixer.music.load(str(full_path))

        # Record what is playing so an idempotent `bgm play` can keep the
        # current track running instead of restarting it.
        save_state(music_type)

        # Play the music
        if repeat == 0:
            # Infinite loop: 0 means loop forever
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: Playing with loops=-1 (infinite)")
            sys.stdout.flush()
            pygame.mixer.music.play(loops=-1)
        else:
            # Play specified number of times (loops parameter is count-1)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: Playing with loops={repeat - 1}")
            sys.stdout.flush()
            pygame.mixer.music.play(loops=repeat - 1)

        # Keep the script running while music plays
        loop_count = 0
        while pygame.mixer.music.get_busy():
            # Check every 0.1 seconds
            time.sleep(0.1)
            loop_count += 1
            # Log every 10 seconds (100 * 0.1s = 10s)
            if loop_count % 100 == 0:
                print(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: Still playing... (loop_count={loop_count})"
                )
                sys.stdout.flush()

    except KeyboardInterrupt:
        click.echo(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Playback stopped by user")
    except pygame.error as e:
        click.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error playing audio: {e}",
            err=True,
        )
    finally:
        # Stop the music and cleanup
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        # Only cleanup PID if we're in daemon mode (current_pid will be in globals)
        # This function is called both from daemon and potentially other contexts
        try:
            current_pid = os.getpid()
            pid_file = get_pid_file()
            if pid_file.exists():
                with open(pid_file, "r") as f:
                    saved_pid = int(f.read().strip())
                if saved_pid == current_pid:
                    cleanup_pid()
                    clear_state()
        except Exception:
            # Fallback: just cleanup
            cleanup_pid()
            clear_state()


def wait_for_daemon_pid(previous_pid: Optional[int], timeout: float = 5.0) -> None:
    """
    Wait for the new daemon to write its PID to the PID file.

    The daemon saves its PID asynchronously after startup. Holding the
    caller's file lock until the PID appears prevents a rapid follow-up
    play/stop call from reading a stale or empty PID file and spawning
    yet another daemon, which would leave orphaned players overlapping.
    """
    pid_file = get_pid_file()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            saved_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            saved_pid = None
        if (
            saved_pid is not None
            and saved_pid != previous_pid
            and ProcessManager.check_process_exists(saved_pid)
        ):
            return
        time.sleep(0.1)


def is_music_type_playing(music_type: str) -> bool:
    """
    Check if a live player daemon is currently playing the given music type.

    Args:
        music_type: Either 'work', 'done', or 'notification'

    Returns:
        True if a live daemon is playing that music type, False otherwise.
    """
    if load_state() != music_type:
        return False

    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return False

    return ProcessManager.check_process_exists(pid)


def _bgm_executable() -> str:
    """
    Resolve the executable used to spawn the BGM daemon.

    An absolute path is required because host applications (e.g. WorkBuddy)
    run their hooks with a sanitized PATH that has no pyenv shims, where a
    bare ``bgm`` fails to resolve. When ``bgm`` itself was launched by a path
    that already names it, ``sys.argv[0]`` carries that path -- but only trust
    it when it actually looks like bgm, so the local development entry point
    (``main.py``) is never spawned as the daemon. The bare name is the last
    resort so a normal shell invocation keeps working unchanged.
    """
    which_path = shutil.which("bgm")
    if which_path:
        return which_path

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and Path(argv0).stem.lower().startswith("bgm"):
        return argv0

    return "bgm"


def start_background_player(music_type: str, loop: int) -> None:
    """
    Start the BGM player in the background as a daemon process.

    Idempotent: if a live daemon is already playing the same music type,
    this is a no-op (the current track keeps playing uninterrupted).

    Args:
        music_type: Either 'work', 'done', or 'notification'
        loop: Number of times to play. 0 for infinite loop, 1+ for specified count.
    """
    # No-op when the requested music is already playing, so hooks on
    # frequent events (e.g. PostToolUse) don't restart the track.
    if is_music_type_playing(music_type):
        return

    lock_file = get_lock_file()

    # Use file lock to prevent concurrent start
    with FileLock(str(lock_file)):
        # Kill any existing BGM player process first
        previous_pid = kill_existing_process()

        # Use subprocess to start a detached background process
        args = [_bgm_executable(), "play", "--daemon", music_type, str(loop)]

        # Start the background process
        if is_windows():
            # On Windows, use CREATE_NO_WINDOW flag
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                args,
                creationflags=DETACHED_PROCESS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            # On Unix-like systems
            subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )

        if previous_pid is not None:
            click.echo("Stopped previous BGM player")
        click.echo("BGM player started in background")

        # Only release the lock once the new daemon owns the PID file,
        # otherwise a concurrent play/stop would kill nothing and start
        # a second daemon (the race that piled up overlapping players).
        wait_for_daemon_pid(previous_pid)

        # Give it a moment to start and save PID
        time.sleep(0.5)

        # Try to read the PID if it was saved
        pid_file = get_pid_file()
        if pid_file.exists():
            try:
                with open(pid_file, "r") as f:
                    pid = f.read().strip()
                    click.echo(f"Background player PID: {pid}")
            except Exception:
                pass


def run_player_daemon(music_type: str, loop: int) -> None:
    """
    Run the player daemon (called with --daemon flag).

    Args:
        music_type: Either 'work', 'done', or 'notification'
        loop: Number of times to play. 0 for infinite loop, 1+ for specified count.
    """
    # Setup logging with automatic rotation
    log_manager = LogManager.get_log_manager(max_lines=1000, keep_lines=500)
    log_manager.setup_daemon_logging()

    # Debug: log the parameters
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: run_player_daemon called with music_type={music_type}, loop={loop}, type(loop)={type(loop)}"
    )

    # Save current PID first
    current_pid = os.getpid()
    save_pid()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] BGM player daemon started (PID: {current_pid})")

    # Register cleanup handler
    def signal_handler(signum, frame):
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Received termination signal, stopping...")
        # Only cleanup PID if it's still ours (prevent deleting newer process's PID)
        try:
            pid_file = get_pid_file()
            if pid_file.exists():
                with open(pid_file, "r") as f:
                    saved_pid = int(f.read().strip())
                if saved_pid == current_pid:
                    cleanup_pid()
                    clear_state()
                else:
                    print(
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] PID file belongs to newer process ({saved_pid}), not cleaning up"
                    )
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error during cleanup: {e}")
        sys.exit(0)

    # Setup signal handlers
    setup_signal_handlers(signal_handler)

    # Load the selected configuration
    selection = load_selection()

    # Play the music
    play_music(selection, music_type, loop)


@click.command()
@click.argument("music_type", type=click.Choice(["work", "done", "notification"]))
@click.argument("loop", type=int, default=1, required=False)
@click.option(
    "--daemon",
    is_flag=True,
    hidden=True,
    help="Run as daemon process (internal use only)",
)
def play(music_type: str, loop: int, daemon: bool):
    """Play music based on saved configuration.

    MUSIC_TYPE: Type of music to play: 'work', 'done', or 'notification'
    LOOP: Number of times to play. 0 for infinite loop, 1+ for specified count. (default: 1)
    """
    # Check if BGM is enabled
    if not is_bgm_enabled():
        click.echo("AI BGM is disabled. Use 'bgm enable' to enable it.")
        return

    if daemon:
        # Running as daemon
        run_player_daemon(music_type, loop)
    else:
        # Start the player in background
        start_background_player(music_type, loop)
