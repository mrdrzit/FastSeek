from __future__ import annotations

import os
from typing import Optional

import cv2
from decord import VideoReader, cpu
from PySide6.QtCore import QObject, Signal, Slot


class ExportWorker(QObject):

    finished = Signal()
    export_finished = Signal(str)
    export_failed = Signal(str)

    def __init__(
        self,
        video_path: str,
        frame_index: int,
        frame_count: int,
        output_root: str,
    ) -> None:
        super().__init__()

        self.video_path = video_path
        self.frame_index = frame_index
        self.frame_count = frame_count
        self.output_root = output_root

    def _compute_filename(self) -> tuple[str, str]:
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]

        output_dir = os.path.join(self.output_root, video_name)
        os.makedirs(output_dir, exist_ok=True)

        pad = len(str(self.frame_count))
        name = f"img{str(self.frame_index).zfill(pad)}.png"

        return output_dir, name

    @Slot()
    def run(self) -> None:
        try:
            vr = VideoReader(self.video_path, ctx=cpu(0))

            index = max(0, min(self.frame_index, len(vr) - 1))
            frame_rgb = vr[index].asnumpy()

            frame_bgr = frame_rgb[:, :, ::-1]

            output_dir, name = self._compute_filename()
            path = os.path.join(output_dir, name)

            cv2.imwrite(path, frame_bgr)

            self.export_finished.emit(path)

        except Exception as exc:
            self.export_failed.emit(str(exc))

        finally:
            self.finished.emit()