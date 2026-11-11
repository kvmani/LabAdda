"""Host figures from /proc; any failure is reported as ProcUnavailable, never as a crash."""

from __future__ import annotations

import os
from pathlib import Path


class ProcUnavailable(Exception):
    """The figure cannot be read on this machine (not Linux, restricted, or a malformed file)."""


class Proc:
    root = Path("/proc")

    def text(self, relative: str) -> str:
        try:
            return (self.root / relative).read_text(encoding="ascii")
        except (OSError, UnicodeDecodeError) as error:
            raise ProcUnavailable(relative) from error

    def process_rss_bytes(self) -> int:
        for line in self.text("self/status").splitlines():
            if line.startswith("VmRSS:"):
                return self._kilobytes(line) * 1024
        raise ProcUnavailable("VmRSS")

    def load_average(self) -> float:
        try:
            return float(self.text("loadavg").split()[0])
        except (ValueError, IndexError) as error:
            raise ProcUnavailable("loadavg") from error

    def cpu_count(self) -> int:
        return os.cpu_count() or 1

    def memory(self) -> tuple[int, int]:
        """Total and available host memory in bytes."""
        found: dict[str, int] = {}
        for line in self.text("meminfo").splitlines():
            name = line.split(":", 1)[0]
            if name in {"MemTotal", "MemAvailable"}:
                found[name] = self._kilobytes(line) * 1024
        if len(found) != 2 or found["MemTotal"] <= 0:
            raise ProcUnavailable("meminfo")
        return found["MemTotal"], found["MemAvailable"]

    @staticmethod
    def _kilobytes(line: str) -> int:
        try:
            return int(line.partition(":")[2].split()[0])
        except (ValueError, IndexError) as error:
            raise ProcUnavailable(line[:20]) from error
