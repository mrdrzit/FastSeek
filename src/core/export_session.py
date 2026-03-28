from __future__ import annotations

import os

import cv2
from decord import VideoReader, cpu


class ExportSession:
    """
    Persistent full-resolution export reader.
    Reuse one VideoReader per loaded video for exact frame export.
    """

    def __init__(self, video_path: str, frame_count: int) -> None:
        self.video_path = video_path
        self.frame_count = frame_count
        self.vr = VideoReader(video_path, ctx=cpu(0))

    def _build_output_path(self, frame_index: int, output_root: str) -> str:
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        output_dir = os.path.join(output_root, video_name)
        os.makedirs(output_dir, exist_ok=True)

        pad = len(str(self.frame_count))
        filename = f"img{str(frame_index).zfill(pad)}.png"
        return os.path.join(output_dir, filename)

    def export_frame_png(self, frame_index: int, output_root: str) -> str:
        index = max(0, min(int(frame_index), self.frame_count - 1))

        frame_rgb = self.vr[index].asnumpy()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        output_path = self._build_output_path(index, output_root)

        ok = cv2.imwrite(output_path, frame_bgr)
        if not ok:
            raise RuntimeError(f"Failed to write image: {output_path}")

        return output_path