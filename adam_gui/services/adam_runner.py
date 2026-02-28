"""ADAM executable subprocess management."""

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional


class AdamRunner:
    """Manages ADAM executable invocation."""

    def __init__(self, executable_path: str):
        self.executable_path = executable_path
        self._process: Optional[subprocess.Popen] = None

    def validate_executable(self) -> tuple[bool, str]:
        path = Path(self.executable_path)
        if not path.exists():
            return False, f"File not found: {self.executable_path}"
        if not os.access(str(path), os.X_OK):
            return False, f"File is not executable: {self.executable_path}"
        return True, "OK"

    def run(
        self,
        param_file: str,
        work_dir: str,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Run ADAM synchronously (call from worker thread). Returns exit code."""
        self._process = subprocess.Popen(
            [self.executable_path, param_file],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self._process.stdout:
            for line in self._process.stdout:
                if on_stdout:
                    on_stdout(line.rstrip())
        self._process.wait()
        # Read any remaining stderr
        if self._process.stderr and on_stderr:
            for line in self._process.stderr:
                on_stderr(line.rstrip())
        return self._process.returncode

    def cancel(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def is_available(path: str) -> bool:
        return Path(path).is_file() and os.access(path, os.X_OK)
