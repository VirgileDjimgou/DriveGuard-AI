from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union

import cv2


@dataclass
class FramePacket:
    frame_index: int
    frame: "cv2.typing.MatLike"
    source_name: str
    timestamp_seconds: float
    fps: float


class BaseVideoSource:
    def open(self) -> None:
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class CaptureVideoSource(BaseVideoSource):
    def __init__(
        self,
        source: Union[int, str],
        width: int = 720,
        height: int = 720,
    ) -> None:
        self.source = source
        self.width = width
        self.height = height
        self._capture: Optional[cv2.VideoCapture] = None
        self._frame_index = 0
        self._fps = 30.0

    def open(self) -> None:
        self._capture = cv2.VideoCapture(self.source)
        if not self._capture.isOpened():
            raise RuntimeError(f"Unable to open video source: {self.source}")

        if isinstance(self.source, int):
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        capture_fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if capture_fps > 0:
            self._fps = capture_fps

    def read(self) -> Optional[FramePacket]:
        if self._capture is None:
            self.open()

        assert self._capture is not None
        success, frame = self._capture.read()
        if not success:
            return None

        packet = FramePacket(
            frame_index=self._frame_index,
            frame=frame,
            source_name=str(self.source),
            timestamp_seconds=self._frame_index / self._fps,
            fps=self._fps,
        )
        self._frame_index += 1
        return packet

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class BatchVideoSource(BaseVideoSource):
    def __init__(self, video_paths: Sequence[Union[str, Path]], width: int = 720, height: int = 720) -> None:
        if not video_paths:
            raise ValueError("BatchVideoSource requires at least one video path.")

        self.video_paths = [str(Path(path)) for path in video_paths]
        self.width = width
        self.height = height
        self._current_index = 0
        self._current_source: Optional[CaptureVideoSource] = None

    def open(self) -> None:
        self._open_current_source()

    def read(self) -> Optional[FramePacket]:
        if self._current_source is None:
            self.open()

        while self._current_source is not None:
            packet = self._current_source.read()
            if packet is not None:
                packet.source_name = self.video_paths[self._current_index]
                return packet

            self._current_source.close()
            self._current_index += 1
            if self._current_index >= len(self.video_paths):
                self._current_source = None
                return None
            self._open_current_source()

        return None

    def close(self) -> None:
        if self._current_source is not None:
            self._current_source.close()
            self._current_source = None

    def _open_current_source(self) -> None:
        self._current_source = CaptureVideoSource(
            source=self.video_paths[self._current_index],
            width=self.width,
            height=self.height,
        )
        self._current_source.open()


def create_video_source(
    mode: str,
    source: Union[int, str, Sequence[Union[str, Path]]],
    width: int = 720,
    height: int = 720,
) -> BaseVideoSource:
    if mode == "webcam":
        return CaptureVideoSource(source=int(source), width=width, height=height)
    if mode == "video":
        return CaptureVideoSource(source=str(source), width=width, height=height)
    if mode == "batch":
        return BatchVideoSource(video_paths=source, width=width, height=height)
    raise ValueError(f"Unsupported source mode: {mode}")
