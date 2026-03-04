"""
Safe Subprocess Execution Utilities

Provides timeout-protected subprocess execution to prevent application hangs.
All subprocess calls in the application should use these utilities.
"""

import subprocess
import logging
import time
import signal
import threading
from typing import Union, List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SubprocessResult:
    """Result container for subprocess execution."""
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

class TimeoutError(Exception):
    """Raised when subprocess execution times out."""
    pass

def run_with_timeout(
    cmd: Union[str, List[str]],
    timeout: int = 300,
    capture_output: bool = True,
    text: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    shell: bool = False
) -> SubprocessResult:
    """
    Execute subprocess with mandatory timeout to prevent hangs.

    Args:
        cmd: Command to execute (string or list)
        timeout: Maximum execution time in seconds (default: 5 minutes)
        capture_output: Whether to capture stdout/stderr
        text: Whether to return text output (vs bytes)
        cwd: Working directory
        env: Environment variables
        shell: Whether to use shell execution

    Returns:
        SubprocessResult with execution details

    Raises:
        TimeoutError: If process exceeds timeout
        subprocess.CalledProcessError: If process exits with non-zero code
    """
    start_time = time.time()

    logger.debug(f"Executing command with {timeout}s timeout: {cmd}")

    try:
        # Use subprocess.run with timeout
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            cwd=cwd,
            env=env,
            shell=shell,
            check=False  # Don't raise on non-zero exit, we'll handle it
        )

        duration = time.time() - start_time

        return SubprocessResult(
            returncode=result.returncode,
            stdout=result.stdout if capture_output else "",
            stderr=result.stderr if capture_output else "",
            duration=duration,
            timed_out=False
        )

    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        logger.error(f"Command timed out after {timeout}s: {cmd}")

        # Return timeout result instead of raising
        return SubprocessResult(
            returncode=-1,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=e.stderr.decode() if e.stderr else "",
            duration=duration,
            timed_out=True
        )

def run_ffmpeg_safe(
    cmd: List[str],
    timeout: int = 600,
    progress_callback: Optional[callable] = None
) -> SubprocessResult:
    """
    Execute FFmpeg command with enhanced safety and optional progress tracking.

    Args:
        cmd: FFmpeg command as list
        timeout: Maximum execution time (default: 10 minutes for video processing)
        progress_callback: Optional callback for progress updates

    Returns:
        SubprocessResult with execution details
    """
    # Ensure FFmpeg is first in command
    if cmd[0] != 'ffmpeg' and 'ffmpeg' not in cmd[0]:
        logger.warning(f"Command doesn't start with ffmpeg: {cmd}")

    # Add common FFmpeg safety flags
    safe_cmd = ['ffmpeg', '-y']  # -y to overwrite output files

    # Add the rest of the command (skip the original 'ffmpeg' if present)
    start_idx = 1 if cmd[0] == 'ffmpeg' else 0
    safe_cmd.extend(cmd[start_idx:])

    logger.info(f"Executing FFmpeg command: {' '.join(safe_cmd)}")

    if progress_callback:
        # Run with progress monitoring
        return _run_with_progress(safe_cmd, timeout, progress_callback)
    else:
        # Standard execution
        return run_with_timeout(safe_cmd, timeout=timeout)

def _run_with_progress(
    cmd: List[str],
    timeout: int,
    progress_callback: callable
) -> SubprocessResult:
    """Execute command with progress monitoring via stderr parsing."""
    start_time = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        stdout_lines = []
        stderr_lines = []

        # Monitor stderr for progress
        while True:
            if process.poll() is not None:
                break

            if time.time() - start_time > timeout:
                process.terminate()
                process.wait(timeout=5)  # Give it 5 seconds to cleanup
                if process.poll() is None:
                    process.kill()  # Force kill if still running

                return SubprocessResult(
                    returncode=-1,
                    stdout="",
                    stderr="Process timed out",
                    duration=time.time() - start_time,
                    timed_out=True
                )

            # Read stderr line for progress
            stderr_line = process.stderr.readline()
            if stderr_line:
                stderr_lines.append(stderr_line.strip())
                if progress_callback:
                    progress_callback(stderr_line.strip())

        # Get remaining output
        remaining_stdout, remaining_stderr = process.communicate()
        if remaining_stdout:
            stdout_lines.append(remaining_stdout.strip())
        if remaining_stderr:
            stderr_lines.append(remaining_stderr.strip())

        duration = time.time() - start_time

        return SubprocessResult(
            returncode=process.returncode,
            stdout='\n'.join(stdout_lines),
            stderr='\n'.join(stderr_lines),
            duration=duration,
            timed_out=False
        )

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return SubprocessResult(
            returncode=-2,
            stdout="",
            stderr=str(e),
            duration=time.time() - start_time,
            timed_out=False
        )

def validate_subprocess_result(result: SubprocessResult, operation_name: str) -> None:
    """
    Validate subprocess result and raise appropriate errors.

    Args:
        result: SubprocessResult to validate
        operation_name: Description of operation for error messages

    Raises:
        TimeoutError: If process timed out
        subprocess.CalledProcessError: If process failed
    """
    if result.timed_out:
        raise TimeoutError(f"{operation_name} timed out after {result.duration:.1f}s")

    if result.returncode != 0:
        error_msg = f"{operation_name} failed with return code {result.returncode}"
        if result.stderr:
            error_msg += f": {result.stderr}"

        # Create CalledProcessError for compatibility
        raise subprocess.CalledProcessError(
            result.returncode,
            operation_name,
            output=result.stdout,
            stderr=result.stderr
        )