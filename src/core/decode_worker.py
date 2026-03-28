from __future__ import annotations

import time
import threading

from collections import deque
from typing import Deque, List, Optional
from PySide6.QtCore import QThread, Signal
from src.core.frame_cache import FrameCache
from src.core.video_session import VideoSession

class DecodeWorker(QThread):
    """
    Background decode worker.

    Rules:
    - main request always has priority
    - latest main request wins
    - prefetch runs only when no urgent request is pending
    """

    frame_ready = Signal(int, object, float, bool)  # index, frame(np.ndarray), latency_ms, cache_hit
    error = Signal(str)

    def __init__(self, session: VideoSession, cache: FrameCache) -> None:
        super().__init__()
        self.session = session
        self.cache = cache

        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)

        self._running = True

        self._pending_index: Optional[int] = None
        self._pending_token: int = 0

        self._prefetch_queue: Deque[int] = deque()
        self._prefetch_seen: set[int] = set()

    def stop(self) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        self.wait()

    def request_frame(self, index: int, prefetch_indices: Optional[List[int]] = None) -> None:
        with self._cv:
            self._pending_index = int(index)
            self._pending_token += 1

            self._prefetch_queue.clear()
            self._prefetch_seen.clear()

            if prefetch_indices:
                for idx in prefetch_indices:
                    idx = int(idx)
                    if idx not in self._prefetch_seen:
                        self._prefetch_queue.append(idx)
                        self._prefetch_seen.add(idx)

            self._cv.notify_all()

    def request_drag_frame(self, index: int) -> None:
        """
        Same as request_frame, but without prefetch refresh.
        Better for high-frequency slider dragging.
        """
        with self._cv:
            self._pending_index = int(index)
            self._pending_token += 1
            self._cv.notify_all()

    def _get_work(self) -> tuple[str, int, int]:
        with self._cv:
            while self._running and self._pending_index is None and not self._prefetch_queue:
                self._cv.wait()

            if not self._running:
                return ("stop", -1, -1)

            if self._pending_index is not None:
                index = self._pending_index
                token = self._pending_token
                self._pending_index = None
                return ("main", index, token)

            index = self._prefetch_queue.popleft()
            self._prefetch_seen.discard(index)
            return ("prefetch", index, -1)

    def run(self) -> None:
        try:
            while True:
                kind, index, token = self._get_work()

                if kind == "stop":
                    return

                index = max(0, min(index, self.session.frame_count - 1))

                cached = self.cache.get(index)
                if cached is not None:
                    if kind == "main":
                        self.frame_ready.emit(index, cached, 0.0, True)
                    continue

                t0 = time.perf_counter()
                frame = self.session.get_frame(index)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                self.cache.put(index, frame)

                if kind == "prefetch":
                    continue

                with self._lock:
                    is_stale = token != self._pending_token and self._pending_index is not None

                if not is_stale:
                    self.frame_ready.emit(index, frame, latency_ms, False)

        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")