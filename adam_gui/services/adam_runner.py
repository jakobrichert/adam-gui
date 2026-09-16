"""ADAM executable subprocess management."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Callable, Optional

DEFAULT_ARGS = "{param_file}"


class AdamRunner:
    """Manages ADAM executable invocation.

    The command line is ``<executable> <args>`` where ``args`` is a template;
    ``{param_file}`` and ``{work_dir}`` are substituted.
    """

    def __init__(self, executable_path: str, args_template: str = DEFAULT_ARGS):
        self.executable_path = executable_path
        self.args_template = args_template or DEFAULT_ARGS
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def validate_executable(self) -> tuple[bool, str]:
        if not self.executable_path:
            return False, "No executable configured"
        path = Path(self.executable_path).expanduser()
        if not path.exists():
            return False, f"File not found: {path}"
        if path.is_dir():
            return False, f"That is a folder, not a program: {path}"
        if not os.access(str(path), os.X_OK):
            return False, f"File is not executable (try chmod +x): {path}"
        return True, "OK"

    def build_command(self, param_file: str, work_dir: str) -> list[str]:
        args = self.args_template.format(param_file=param_file, work_dir=work_dir)
        return [str(Path(self.executable_path).expanduser())] + shlex.split(args)

    def run(
        self,
        param_file: str,
        work_dir: str,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Run ADAM synchronously (call from a worker thread). Returns the exit code.

        stderr is merged into stdout so a chatty process can never block on a
        full pipe; ``on_stderr`` is kept for API compatibility and unused.
        Output is also written to ``<work_dir>/adam.log``.
        """
        self._cancelled = False
        cmd = self.build_command(param_file, work_dir)
        log_path = Path(work_dir) / "adam.log"
        self._process = subprocess.Popen(
            cmd,
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            errors="replace",
        )
        with open(log_path, "w", encoding="utf-8") as log:
            assert self._process.stdout is not None
            for line in self._process.stdout:
                log.write(line)
                if on_stdout:
                    on_stdout(line.rstrip("\n"))
        self._process.wait()
        return self._process.returncode

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def is_available(path: str) -> bool:
        if not path:
            return False
        p = Path(path).expanduser()
        return p.is_file() and os.access(p, os.X_OK)
