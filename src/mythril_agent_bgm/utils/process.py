#!/usr/bin/env python3
"""
Cross-platform process management utilities.
Handles process signals and lifecycle with platform-specific implementations.
"""

import os
import signal
import time
from typing import Optional

from mythril_agent_bgm.utils.platform_utils import is_windows, is_unix

# Import fcntl only on Unix-like systems
if is_unix():
    import fcntl


class ProcessManager:
    """Manages process operations with cross-platform compatibility."""

    @staticmethod
    def check_process_exists(pid: int) -> bool:
        """
        Check if a process with given PID exists.

        Args:
            pid: Process ID to check

        Returns:
            True if process exists, False otherwise
        """
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except (PermissionError, OSError):
            # Process exists but we don't have permission
            return True

    @staticmethod
    def kill_process(pid: int, graceful: bool = True, timeout: float = 2.0) -> bool:
        """
        Kill a process with platform-appropriate signals.

        Args:
            pid: Process ID to kill
            graceful: If True, try graceful shutdown first
            timeout: Seconds to wait for graceful shutdown

        Returns:
            True if process was killed, False if it doesn't exist or failed
        """
        if not ProcessManager.check_process_exists(pid):
            return False

        try:
            if is_windows():
                return ProcessManager._kill_windows(pid, graceful, timeout)
            else:
                return ProcessManager._kill_unix(pid, graceful, timeout)
        except (PermissionError, OSError):
            return False

    @staticmethod
    def _kill_windows(pid: int, graceful: bool, timeout: float) -> bool:
        """Kill process on Windows."""
        # Windows: SIGTERM is supported, but SIGKILL is not
        os.kill(pid, signal.SIGTERM)

        if graceful:
            # Wait for graceful shutdown
            elapsed = 0.0
            while elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
                if not ProcessManager.check_process_exists(pid):
                    return True

            # Try CTRL_BREAK_EVENT if SIGTERM didn't work
            try:
                if hasattr(signal, "CTRL_BREAK_EVENT"):
                    os.kill(pid, signal.CTRL_BREAK_EVENT)
                    time.sleep(0.2)
            except (ProcessLookupError, AttributeError, OSError):
                pass

        return not ProcessManager.check_process_exists(pid)

    @staticmethod
    def _kill_unix(pid: int, graceful: bool, timeout: float) -> bool:
        """Kill process on Unix-like systems."""
        # Unix: use SIGTERM then SIGKILL
        os.kill(pid, signal.SIGTERM)

        if graceful:
            # Wait for graceful shutdown
            elapsed = 0.0
            while elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
                if not ProcessManager.check_process_exists(pid):
                    return True

            # Force kill if still running
            try:
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.2)
            except ProcessLookupError:
                pass

        return not ProcessManager.check_process_exists(pid)


class FileLock:
    """Cross-platform file locking (Unix only, no-op on Windows)."""

    def __init__(self, lock_file_path: str):
        """
        Initialize file lock.

        Args:
            lock_file_path: Path to the lock file
        """
        self.lock_file_path = lock_file_path
        self.lock_fd: Optional[int] = None

    def __enter__(self):
        """Acquire the lock."""
        if is_unix():
            self.lock_fd = os.open(self.lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        # On Windows, no file locking - just return
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release the lock."""
        if self.lock_fd is not None and is_unix():
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            self.lock_fd = None


def setup_signal_handlers(handler_func) -> None:
    """
    Setup signal handlers for graceful shutdown.

    Args:
        handler_func: Function to call when signal is received
    """
    # SIGINT (Ctrl+C) works on all platforms
    signal.signal(signal.SIGINT, handler_func)

    # SIGTERM is available on all platforms but behavior differs
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler_func)
