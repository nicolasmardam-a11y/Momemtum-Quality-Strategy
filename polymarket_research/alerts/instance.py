"""One monitor process per database.

Two processes on one DB (overlapping cron ``--once`` runs, or a manual ``--once``
next to the loop) would each run ``Dispatcher.recover_inflight()`` at startup and
re-queue the other process's in-flight sends, so an alert could be delivered twice,
and they would double the polling load. ``InstanceLock`` takes an exclusive,
non-blocking ``flock`` on ``<db>.lock``; the kernel releases it when the process
exits, however it exits, so a crash never leaves a stale lock behind.
``--report`` is read-only and does not take the lock.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    import fcntl
except ImportError:          # not POSIX (Windows): no lock available, see InstanceLock.acquire
    fcntl = None  # type: ignore[assignment]


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(f"{db_path}.lock")
        self._fd: int | None = None

    def acquire(self) -> None:
        """Take the lock or raise AlreadyRunning (never waits)."""
        if fcntl is None:
            raise AlreadyRunning("file locking (fcntl) is unavailable on this platform; refusing to run "
                                 "without a single-instance guard")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder = os.read(fd, 32).decode(errors="replace").strip() or "unknown"
            os.close(fd)
            raise AlreadyRunning(f"another monitor process (pid {holder}) is using this database "
                                 f"({self.path} is locked)") from None
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        self._fd = fd

    def release(self) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
