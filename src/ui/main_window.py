from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QImage, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLineEdit,
    QProgressBar,
)

from src.core.frame_cache import FrameCache
from src.core.video_session import VideoSession
from src.core.decode_worker import DecodeWorker
from src.core.loader_worker import LoaderWorker, LoadResult
from src.core.export_worker import ExportWorker
from src.core.export_session import ExportSession


class VideoViewer(QWidget):
    def __init__(self, video_path: Optional[str] = None) -> None:
        super().__init__()

        self.setWindowTitle("Fast Decord Frame Viewer")
        self.resize(1100, 800)

        self.export_session: Optional[ExportSession] = None
        self.session: Optional[VideoSession] = None
        self.cache: Optional[FrameCache] = None
        self.worker: Optional[DecodeWorker] = None

        self.loader_thread: Optional[QThread] = None
        self.loader_worker: Optional[LoaderWorker] = None
        self.is_loading = False

        self.export_thread = None
        self.export_worker = None

        self.current_index = 0
        self.last_requested_index = 0
        self.drag_pending_index: Optional[int] = None

        self.drag_timer = QTimer(self)
        self.drag_timer.setInterval(33)  # ~30 fps max
        self.drag_timer.timeout.connect(self._flush_drag_request)

        self.image_label = QLabel("Open a video")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)
        self.image_label.setStyleSheet("background: #111; color: #ddd;")

        self.loading_main_label = QLabel("Loading video...")
        self.loading_main_label.setAlignment(Qt.AlignCenter)
        self.loading_stage_label = QLabel("Starting")
        self.loading_stage_label.setAlignment(Qt.AlignCenter)

        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setRange(0, 100)
        self.loading_progress_bar.setValue(0)

        self.info_label = QLabel("No video loaded")
        self.status_label = QLabel("Idle")

        self.open_button = QPushButton("Open")
        self.prev_button = QPushButton("<<")
        self.next_button = QPushButton(">>")
        self.export_button = QPushButton("Export Frame")

        self.frame_edit = QLineEdit()
        self.frame_edit.setPlaceholderText("Frame #")
        self.frame_edit.setFixedWidth(120)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setTracking(True)

        top_row = QHBoxLayout()
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.prev_button)
        top_row.addWidget(self.next_button)
        top_row.addWidget(self.frame_edit)
        top_row.addWidget(self.export_button)
        top_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.image_label, stretch=1)
        layout.addWidget(self.loading_main_label)
        layout.addWidget(self.loading_stage_label)
        layout.addWidget(self.loading_progress_bar)
        layout.addWidget(self.slider)
        layout.addWidget(self.info_label)
        layout.addWidget(self.status_label)

        self.open_button.clicked.connect(self.open_dialog)
        self.prev_button.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(+1))
        self.frame_edit.returnPressed.connect(self.jump_to_frame)
        self.export_button.clicked.connect(self.export_current_frame)

        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.slider.sliderReleased.connect(self._on_slider_released)

        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self.step(+1))
        QShortcut(QKeySequence("Shift+Left"), self, activated=lambda: self.step(-10))
        QShortcut(QKeySequence("Shift+Right"), self, activated=lambda: self.step(+10))
        QShortcut(QKeySequence("Ctrl+Left"), self, activated=lambda: self.step(-100))
        QShortcut(QKeySequence("Ctrl+Right"), self, activated=lambda: self.step(+100))

        self._set_loading_widgets_visible(False)
        self._set_navigation_enabled(False)

        if video_path:
            self.start_video_load(video_path)

    def closeEvent(self, event) -> None:
        self._cleanup_loader()
        self._cleanup_decode_worker()
        self._cleanup_export_session()
        super().closeEvent(event)

    def open_dialog(self) -> None:
        if self.is_loading:
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;All files (*)",
        )
        if path:
            self.start_video_load(path)

    def _set_loading_widgets_visible(self, visible: bool) -> None:
        self.loading_main_label.setVisible(visible)
        self.loading_stage_label.setVisible(visible)
        self.loading_progress_bar.setVisible(visible)

    def _set_navigation_enabled(self, enabled: bool) -> None:
        self.prev_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.frame_edit.setEnabled(enabled)
        self.export_button.setEnabled(enabled)

    def _cleanup_decode_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    def _cleanup_loader(self) -> None:
        thread = self.loader_thread
        worker = self.loader_worker

        self.loader_thread = None
        self.loader_worker = None

        if worker is not None:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass

        if thread is not None:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait()
            except RuntimeError:
                pass

    def _on_loader_thread_finished(self) -> None:
        self.loader_thread = None
        self.loader_worker = None

    def enter_loading_state(self) -> None:
        self.is_loading = True
        self.drag_timer.stop()
        self.drag_pending_index = None

        self._set_navigation_enabled(False)
        self.open_button.setEnabled(False)

        self.loading_main_label.setText("Loading video...")
        self.loading_stage_label.setText("Starting")
        self.loading_progress_bar.setValue(0)
        self._set_loading_widgets_visible(True)

        self.status_label.setText("Loading...")
        self.image_label.setText("Loading video...")
        self.image_label.setPixmap(QPixmap())

    def exit_loading_state(self) -> None:
        self.is_loading = False
        self._set_loading_widgets_visible(False)
        self.open_button.setEnabled(True)

    def update_loading_progress(self, percent: int, main_text: str, stage_text: str) -> None:
        self.loading_progress_bar.setValue(percent)
        self.loading_main_label.setText(main_text)
        self.loading_stage_label.setText(stage_text)
        self.status_label.setText(stage_text)

    def start_video_load(self, path: str) -> None:
        self._cleanup_loader()
        self._cleanup_decode_worker()
        self._cleanup_export_session()

        self.session = None
        self.cache = None
        self.current_index = 0
        self.last_requested_index = 0

        self.enter_loading_state()

        self.loader_thread = QThread(self)
        self.loader_worker = LoaderWorker(path=path, preview_width=960)
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_worker.progress_changed.connect(self.update_loading_progress)
        self.loader_worker.load_finished.connect(self.handle_load_finished)
        self.loader_worker.load_failed.connect(self.handle_load_failed)
        self.loader_worker.finished.connect(self.loader_thread.quit)
        self.loader_worker.finished.connect(self.loader_worker.deleteLater)
        self.loader_thread.finished.connect(self._on_loader_thread_finished)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)

        self.loader_thread.start()

    def handle_load_finished(self, result: LoadResult) -> None:
        try:
            self._cleanup_decode_worker()
            self._cleanup_export_session()

            self.session = VideoSession(
                path=result.path,
                preview_width=result.preview_width,
                preview_height=result.preview_height,
                frame_count=result.frame_count,
                width=result.width,
                height=result.height,
                fps=result.fps,
            )
            self.cache = FrameCache(capacity=200)
            self.cache.put(0, result.first_frame_rgb)

            self.export_session = ExportSession(
                video_path=result.path,
                frame_count=result.frame_count,
            )

            self.worker = DecodeWorker(self.session, self.cache)
            self.worker.frame_ready.connect(self._on_frame_ready)
            self.worker.error.connect(self._on_worker_error)
            self.worker.start()

            self.slider.setMaximum(max(0, result.frame_count - 1))
            self.current_index = 0
            self.last_requested_index = 0

            self.info_label.setText(
                f"{os.path.basename(result.path)} | "
                f"{result.width}x{result.height} | "
                f"{result.frame_count} frames | "
                f"{result.fps:.3f} fps | "
                f"preview {result.preview_width}x{result.preview_height}"
            )

            self._display_frame_rgb(result.first_frame_rgb)
            self.status_label.setText("Loaded")
            self._set_navigation_enabled(True)
        except Exception as exc:
            self.handle_load_failed(f"Could not finalize loaded video: {exc}")
            return
        finally:
            self.exit_loading_state()

    def handle_load_failed(self, message: str) -> None:
        self.session = None
        self.cache = None
        self._cleanup_decode_worker()
        self._cleanup_export_session()
        self._set_navigation_enabled(False)
        self.status_label.setText(message)
        self.info_label.setText("No video loaded")
        self.image_label.setText("Open a video")
        self.image_label.setPixmap(QPixmap())
        self.exit_loading_state()

    def _build_prefetch_window(self, index: int) -> List[int]:
        if self.session is None:
            return []

        direction = 1 if index >= self.last_requested_index else -1
        frame_count = self.session.frame_count

        if direction >= 0:
            back_n = 5
            fwd_n = 20
        else:
            back_n = 20
            fwd_n = 5

        indices = []

        for i in range(index - back_n, index):
            if 0 <= i < frame_count:
                indices.append(i)

        for i in range(index + 1, index + 1 + fwd_n):
            if 0 <= i < frame_count:
                indices.append(i)

        return indices

    def request_frame(self, index: int, settled: bool) -> None:
        if self.is_loading:
            return
        if self.session is None or self.worker is None:
            return

        index = max(0, min(index, self.session.frame_count - 1))

        if settled:
            prefetch = self._build_prefetch_window(index)
            self.worker.request_frame(index, prefetch_indices=prefetch)
        else:
            self.worker.request_drag_frame(index)

        self.last_requested_index = index
        self.status_label.setText(f"Requesting frame {index}...")

    def step(self, delta: int) -> None:
        if self.is_loading or self.session is None:
            return
        target = max(0, min(self.current_index + delta, self.session.frame_count - 1))
        self.slider.setValue(target)
        self.request_frame(target, settled=True)

    def jump_to_frame(self) -> None:
        if self.is_loading or self.session is None:
            return

        text = self.frame_edit.text().strip()
        if not text:
            return

        try:
            target = int(text)
        except ValueError:
            self.status_label.setText("Invalid frame number")
            return

        target = max(0, min(target, self.session.frame_count - 1))
        self.slider.setValue(target)
        self.request_frame(target, settled=True)

    def _on_slider_pressed(self) -> None:
        if self.is_loading:
            return
        self.drag_pending_index = self.slider.value()

    def _on_slider_moved(self, value: int) -> None:
        if self.is_loading:
            return
        self.drag_pending_index = value
        if not self.drag_timer.isActive():
            self.drag_timer.start()

    def _on_slider_released(self) -> None:
        if self.is_loading:
            return
        self.drag_timer.stop()
        value = self.slider.value()
        self.drag_pending_index = None
        self.request_frame(value, settled=True)

    def _flush_drag_request(self) -> None:
        if self.is_loading:
            return
        if self.drag_pending_index is None:
            return
        self.request_frame(self.drag_pending_index, settled=False)

    def _numpy_to_pixmap(self, frame_rgb: np.ndarray) -> QPixmap:
        frame_rgb = np.ascontiguousarray(frame_rgb)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _display_frame_rgb(self, frame_rgb: np.ndarray) -> None:
        pixmap = self._numpy_to_pixmap(frame_rgb)
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _on_frame_ready(self, index: int, frame_rgb: np.ndarray, latency_ms: float, cache_hit: bool) -> None:
        self.current_index = index

        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)

        self._display_frame_rgb(frame_rgb)

        cache_size = len(self.cache) if self.cache is not None else 0
        source = "cache" if cache_hit else "decode"
        self.status_label.setText(
            f"Frame {index} | {source} | {latency_ms:.1f} ms | cache size: {cache_size}"
        )

    def _cleanup_export_session(self) -> None:
        self.export_session = None

    def _on_export_finished(self, path: str) -> None:
        self.status_label.setText(f"Exported: {path}")

    def _on_export_failed(self, message: str) -> None:
        self.status_label.setText(f"Export failed: {message}")

    def _on_worker_error(self, message: str) -> None:
        self.status_label.setText(f"Worker error: {message}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        pixmap = self.image_label.pixmap()
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)

    def export_current_frame(self) -> None:

        if self.session is None:
            return

        output_root = QFileDialog.getExistingDirectory(
            self,
            "Select export folder",
        )

        if not output_root:
            return

        frame_index = self.current_index
        frame_count = self.session.frame_count
        video_path = self.session.path

        self.export_thread = QThread(self)
        self.export_worker = ExportWorker(
            video_path,
            frame_index,
            frame_count,
            output_root,
        )

        self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.export_finished.connect(self._on_export_finished)
        self.export_worker.export_failed.connect(self._on_export_failed)
        self.export_worker.finished.connect(self.export_thread.quit)
        self.export_worker.finished.connect(self.export_worker.deleteLater)
        self.export_thread.finished.connect(self.export_thread.deleteLater)
        self.export_thread.start()