from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np
from decord import VideoReader, cpu


@dataclass
class VideoMetadata:
    path: str
    frame_count: int
    width: int
    height: int
    fps: float


class VideoSession:
    """
    Synchronous Decord wrapper.
    Threading/caching stay outside this class.

    Source/original metadata are stored in:
    - self.width
    - self.height

    Interactive browsing uses a preview-sized reader:
    - self.preview_width
    - self.preview_height
    """

    def __init__(
        self,
        path: str,
        *,
        preview_width: Optional[int] = None,
        preview_height: Optional[int] = None,
        frame_count: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[float] = None,
    ) -> None:
        self.path = path
        self.preview_width = preview_width
        self.preview_height = preview_height

        reader_kwargs = {"ctx": cpu(0)}
        if preview_width is not None and preview_height is not None:
            reader_kwargs["width"] = int(preview_width)
            reader_kwargs["height"] = int(preview_height)

        self.vr = VideoReader(path, **reader_kwargs)

        if frame_count is None:
            frame_count = len(self.vr)

        if width is None or height is None:
            # Fall back to reading source dims only if metadata was not provided.
            # Note: if the reader is preview-sized, this fallback reflects preview
            # dimensions, so the loader should normally provide source dims.
            first = self.vr[0].asnumpy()
            height, width = first.shape[:2]

        if fps is None:
            try:
                fps = float(self.vr.get_avg_fps())
            except Exception:
                fps = 0.0

        self.frame_count = int(frame_count)
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)

    def get_metadata(self) -> VideoMetadata:
        return VideoMetadata(
            path=self.path,
            frame_count=self.frame_count,
            width=self.width,
            height=self.height,
            fps=self.fps,
        )

    def get_frame(self, index: int) -> np.ndarray:
        index = max(0, min(index, self.frame_count - 1))
        return self.vr[index].asnumpy()  # already preview-sized RGB

    def get_batch(self, indices: Iterable[int]) -> List[np.ndarray]:
        cleaned = []
        for idx in indices:
            idx = max(0, min(int(idx), self.frame_count - 1))
            cleaned.append(idx)

        if not cleaned:
            return []

        batch = self.vr.get_batch(cleaned).asnumpy()  # already preview-sized RGB
        return [frame for frame in batch]