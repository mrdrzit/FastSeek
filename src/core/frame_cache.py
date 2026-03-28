from __future__ import annotations

from collections import OrderedDict
from typing import Optional

import numpy as np

class FrameCache:
    """
    Simple LRU cache storing preview RGB numpy arrays by frame index.
    """

    def __init__(self, capacity: int = 200) -> None:
        self.capacity = max(1, capacity)
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()

    def get(self, index: int) -> Optional[np.ndarray]:
        frame = self._cache.get(index)
        if frame is None:
            return None
        self._cache.move_to_end(index)
        return frame

    def put(self, index: int, frame: np.ndarray) -> None:
        self._cache[index] = frame
        self._cache.move_to_end(index)

        while len(self._cache) > self.capacity:
            self._cache.popitem(last=False)

    def contains(self, index: int) -> bool:
        return index in self._cache

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)