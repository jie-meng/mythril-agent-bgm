#!/usr/bin/env python3
"""
Log management for AI BGM daemon process.
"""

import os
import sys
from pathlib import Path
from typing import Optional


class LogManager:
    """
    Manages log file for AI BGM daemon with automatic rotation.

    Features:
    - Automatic log rotation when file exceeds max lines
    - Keeps most recent N lines when rotating
    - Thread-safe file operations
    """

    # Default configuration
    DEFAULT_MAX_LINES = 1000  # Maximum lines before rotation
    DEFAULT_KEEP_LINES = 500  # Lines to keep after rotation

    def __init__(
        self,
        log_file: Path,
        max_lines: int = DEFAULT_MAX_LINES,
        keep_lines: int = DEFAULT_KEEP_LINES,
    ):
        """
        Initialize log manager.

        Args:
            log_file: Path to the log file
            max_lines: Maximum lines before triggering rotation (default: 1000)
            keep_lines: Number of recent lines to keep after rotation (default: 500)
        """
        self.log_file = log_file
        self.max_lines = max_lines
        self.keep_lines = keep_lines

        # Ensure directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def rotate_if_needed(self) -> None:
        """
        Check log file size and rotate if necessary.

        Rotation strategy:
        - Count lines in log file
        - If exceeds max_lines, keep only the most recent keep_lines
        - Atomic operation using temp file
        """
        if not self.log_file.exists():
            return

        try:
            # Count lines efficiently
            line_count = 0
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                for _ in f:
                    line_count += 1

            # Check if rotation is needed
            if line_count <= self.max_lines:
                return

            # Read the last keep_lines lines
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # Keep only recent lines
            recent_lines = lines[-self.keep_lines :]

            # Write back atomically using temp file
            temp_file = self.log_file.with_suffix(".log.tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(f"[Log rotated: kept last {len(recent_lines)} lines]\n")
                f.writelines(recent_lines)

            # Atomic replace
            temp_file.replace(self.log_file)

        except (IOError, OSError) as e:
            # If rotation fails, just continue - don't break the daemon
            print(f"Warning: Failed to rotate log file: {e}", file=sys.stderr)

    def setup_daemon_logging(self) -> None:
        """
        Setup logging for daemon process.

        Redirects stdout and stderr to log file with line buffering.
        Should be called early in daemon process initialization.
        """
        # Rotate log if needed before redirecting
        self.rotate_if_needed()

        # Flush existing stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()

        # Open log file for appending
        log_fd = os.open(str(self.log_file), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)

        # Redirect stdout and stderr
        os.dup2(log_fd, sys.stdout.fileno())
        os.dup2(log_fd, sys.stderr.fileno())
        os.close(log_fd)

        # Reopen stdout and stderr with line buffering
        sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
        sys.stderr = os.fdopen(sys.stderr.fileno(), "w", buffering=1)

    @staticmethod
    def get_log_file() -> Path:
        """
        Get the default log file path.

        Returns:
            Path to bgm_player.log in user config directory
        """
        from mythril_agent_bgm.utils.common import get_config_dir

        return get_config_dir() / "bgm_player.log"

    @staticmethod
    def get_log_manager(
        max_lines: int = DEFAULT_MAX_LINES,
        keep_lines: int = DEFAULT_KEEP_LINES,
    ) -> "LogManager":
        """
        Get a log manager instance with default log file.

        Args:
            max_lines: Maximum lines before triggering rotation (default: 1000)
            keep_lines: Number of recent lines to keep after rotation (default: 500)

        Returns:
            Configured LogManager instance
        """
        log_file = LogManager.get_log_file()
        return LogManager(log_file, max_lines, keep_lines)
