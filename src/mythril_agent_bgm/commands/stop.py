#!/usr/bin/env python3
"""
Stop music command for AI BGM.
"""

import subprocess
from pathlib import Path

import click

from mythril_agent_bgm.utils.common import get_pid_file, get_lock_file
from mythril_agent_bgm.utils.process import ProcessManager, FileLock
from mythril_agent_bgm.utils.platform_utils import is_unix


def kill_existing_player() -> bool:
    """
    Kill all existing BGM player processes.

    Returns:
        True if at least one process was killed, False otherwise.
    """
    killed_any = False
    pid_file = get_pid_file()

    # Kill all processes matching bgm play --daemon (Unix only - uses pgrep)
    if is_unix():
        killed_any = _kill_all_daemon_processes()
        if killed_any:
            # Clean up PID file
            if pid_file.exists():
                try:
                    pid_file.unlink()
                except (FileNotFoundError, PermissionError):
                    pass
            return True

    # Fallback: Use PID file method (works on all platforms)
    if not pid_file.exists():
        return False

    try:
        with open(pid_file, "r") as f:
            old_pid = int(f.read().strip())

        # Kill the process using ProcessManager
        killed = ProcessManager.kill_process(old_pid, graceful=True, timeout=2.0)
        if killed:
            killed_any = True
    except (ValueError, IOError):
        pass

    # Clean up PID file
    if pid_file.exists():
        try:
            pid_file.unlink()
        except (FileNotFoundError, PermissionError):
            pass

    return killed_any


def _kill_all_daemon_processes() -> bool:
    """
    Kill all daemon processes using pgrep (Unix only).

    Returns:
        True if processes were killed, False otherwise.
    """
    try:
        # Use pgrep to find all bgm daemon processes
        result = subprocess.run(
            ["pgrep", "-f", "bgm play --daemon"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = [int(pid) for pid in result.stdout.strip().split("\n")]
            killed_any = False

            for pid in pids:
                if ProcessManager.kill_process(pid, graceful=True, timeout=2.0):
                    killed_any = True

            return killed_any
    except (FileNotFoundError, subprocess.SubprocessError):
        # pgrep not available
        pass

    return False


@click.command()
def stop():
    """Stop any playing music."""
    lock_file = get_lock_file()

    # Use file lock to prevent race with concurrent start
    with FileLock(str(lock_file)):
        # Kill any existing BGM player process
        killed = kill_existing_player()
        if killed:
            click.echo("Stopped BGM player")
        else:
            click.echo("No BGM player is currently running")
