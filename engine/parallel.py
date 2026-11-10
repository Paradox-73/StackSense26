"""Optional worker processes for the 'Ask next' card.

That card re-runs the engine about 90 times (one run per plausible answer of each open question). The
runs are independent, so on a machine with spare cores they are spread over a few worker processes.
Every run is the same function as without workers (`sensitivity.picks_for`), so the answers do not change.
With fewer than 4 cores, with STACKSENSE_WORKERS=0, or if the workers cannot start, the runs happen in
the calling process instead.
"""
from __future__ import annotations

import multiprocessing
import os
import threading
from concurrent.futures import ProcessPoolExecutor

_POOL: ProcessPoolExecutor | None = None
_FAILED = False
_LOCK = threading.Lock()


def worker_count() -> int:
    """STACKSENSE_WORKERS if set, else 5 or fewer (leaving 2 cores free), and none below 4 cores or under pytest."""
    env = os.environ.get("STACKSENSE_WORKERS")
    if env is not None:
        try:
            return max(0, int(env))
        except ValueError:
            return 0
    if "PYTEST_CURRENT_TEST" in os.environ:
        return 0
    cores = os.cpu_count() or 1
    return 0 if cores < 4 else min(5, cores - 2)


def _exit_with_parent() -> None:
    parent = multiprocessing.parent_process()
    if parent is not None:
        parent.join()  # returns when the server process ends, however it ended
        os._exit(0)


def _start_worker() -> None:
    threading.Thread(target=_exit_with_parent, daemon=True).start()  # a killed server must not leave workers behind
    from . import recommender  # noqa: F401  (loads the knowledge base before the first request)
    from .kb import load_kb
    load_kb()


def _noop(_: int) -> int:
    return 0


def get_pool() -> ProcessPoolExecutor | None:
    """The shared worker pool, started on first use; None when workers are off or could not start."""
    global _POOL, _FAILED
    if _FAILED:
        return None
    with _LOCK:
        if _POOL is None and not _FAILED:
            n = worker_count()
            if n < 2:
                _FAILED = True
                return None
            try:
                _POOL = ProcessPoolExecutor(max_workers=n, initializer=_start_worker,
                                          mp_context=multiprocessing.get_context("spawn"))  # fork is unsafe in a threaded server
                list(_POOL.map(_noop, range(n)))  # start every worker now, not during a request
            except Exception:  # no permission to start processes, or a frozen build: run in-process
                _POOL = None
                _FAILED = True
        return _POOL


def shutdown() -> None:
    global _POOL
    with _LOCK:
        pool, _POOL = _POOL, None
    if pool is not None:
        pool.shutdown(wait=False, cancel_futures=True)
