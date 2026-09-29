"""Soccer-specific neural perception; image-space observations remain separate from state."""

from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".local/ultralytics"
CONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(CONFIG))


@dataclass
class Detection:
    box: list[float]
    confidence: float
    kind: str

    @property
    def foot(self):
        return np.array([(self.box[0] + self.box[2]) / 2, self.box[3]], dtype=float)

    @property
    def center(self):
        return np.array(
            [(self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2], dtype=float
        )


class SoccerModels:
    def __init__(self, directory: Path = ROOT / "models", device="cpu"):
        from ultralytics import YOLO
        import torch

        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.device = device
        self.players = YOLO(str(directory / "football-player-detection.pt"))
        self.ball = YOLO(str(directory / "football-ball-detection.pt"))
        self.pitch = YOLO(str(directory / "football-pitch-detection.pt"))

    def detect(self, image: np.ndarray, previous_ball=None, frame_index=0):
        result = self.players.predict(
            image, imgsz=960, conf=0.25, iou=0.5, device=self.device, verbose=False
        )[0]
        detections = [
            Detection(row[:4].tolist(), float(row[4]), result.names[int(row[5])])
            for row in result.boxes.data.cpu().numpy()
        ]
        balls = [d for d in detections if d.kind == "ball"]
        # Global reacquisition each second; a full-resolution temporal crop in between
        # preserves the small ball's pixels without paying for repeated full-frame inference.
        h, w = image.shape[:2]
        if previous_ball is not None and frame_index % 5 != 0:
            cx, cy = previous_ball
            size = min(640, max(w, h))
            x = max(0, min(w - size, int(cx - size / 2)))
            y = max(0, min(h - size, int(cy - size / 2)))
            crop = image[y : min(h, y + size), x : min(w, x + size)]
            ball_result = self.ball.predict(
                crop, imgsz=640, conf=0.1, device=self.device, verbose=False
            )[0]
            for row in ball_result.boxes.data.cpu().numpy():
                balls.append(
                    Detection(
                        [
                            float(row[0] + x),
                            float(row[1] + y),
                            float(row[2] + x),
                            float(row[3] + y),
                        ],
                        float(row[4]),
                        "ball",
                    )
                )
        else:
            ball_result = self.ball.predict(
                image, imgsz=1280, conf=0.1, device=self.device, verbose=False
            )[0]
            balls.extend(
                Detection(row[:4].tolist(), float(row[4]), "ball")
                for row in ball_result.boxes.data.cpu().numpy()
            )
        # High-resolution overlapping tiles recover fast/airborne balls that leave the
        # temporal crop or disappear when the full broadcast frame is downsampled.
        if max((d.confidence for d in balls), default=0) < 0.35:
            for top in (0, max(0, h // 2 - 80)):
                for left in (0, max(0, w // 2 - 80)):
                    tile = image[top : min(h, top + h // 2 + 80), left : min(w, left + w // 2 + 80)]
                    tiled = self.ball.predict(
                        tile, imgsz=960, conf=0.15, device=self.device, verbose=False
                    )[0]
                    for row in tiled.boxes.data.cpu().numpy():
                        balls.append(
                            Detection(
                                [
                                    float(row[0] + left),
                                    float(row[1] + top),
                                    float(row[2] + left),
                                    float(row[3] + top),
                                ],
                                float(row[4]),
                                "ball",
                            )
                        )
        # Ignore broadcast graphics, large white blobs, and improbable object dimensions.
        balls = [
            d
            for d in balls
            if 2 <= d.box[2] - d.box[0] <= w * 0.025
            and 2 <= d.box[3] - d.box[1] <= h * 0.045
            and d.center[1] > h * 0.12
        ]
        pitch_result = self.pitch.predict(
            image, imgsz=640, conf=0.3, device=self.device, verbose=False
        )[0]
        keypoints = (
            pitch_result.keypoints.data.cpu().numpy()[0]
            if pitch_result.keypoints is not None and len(pitch_result.keypoints.data)
            else np.empty((0, 3))
        )
        return (
            [d for d in detections if d.kind in ("player", "goalkeeper", "referee")],
            balls,
            keypoints,
        )


def kit_feature(image, box):
    """Torso Lab color after removing green/background pixels; independent of kit color names."""
    x1, y1, x2, y2 = map(int, box)
    h, w = image.shape[:2]
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    crop = image[y1 + max(0, (y2 - y1) // 6) : y1 + max(1, (y2 - y1) // 2), x1:x2]
    if crop.size < 12:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ~((hsv[:, :, 0] > 25) & (hsv[:, :, 0] < 95) & (hsv[:, :, 1] > 45))
    pixels = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)[mask]
    if len(pixels) < 3:
        return None
    return np.median(pixels, axis=0).astype(float) / 255


class TeamClassifier:
    def __init__(self):
        self.centers = None
        self.votes = {}
        self.palette = ["#c5ef86", "#91a5ef"]

    def fit(self, features):
        values = np.array([f for f in features if f is not None])
        if len(values) < 6:
            return
        from sklearn.cluster import KMeans

        km = KMeans(n_clusters=2, n_init=10, random_state=17).fit(values)
        # Deterministic ordering: darker kit is Team A; these are not asserted home/away identities.
        self.centers = km.cluster_centers_[np.argsort(km.cluster_centers_[:, 0])]
        if np.linalg.norm(self.centers[0] - self.centers[1]) < 0.10:
            self.centers = None

    def classify(self, track_id, feature):
        if self.centers is None or feature is None:
            return "unknown", 0.0
        dist = np.linalg.norm(self.centers - feature, axis=1)
        if min(dist) > 0.36:
            return "unknown", 0.0
        confidence = float(np.clip((max(dist) - min(dist)) / (max(dist) + 1e-6), 0, 1))
        vote = self.votes.setdefault(track_id, np.zeros(2))
        vote *= 0.96
        vote[int(np.argmin(dist))] += confidence
        team = int(np.argmax(vote))
        return ("home" if team == 0 else "away"), round(
            float(vote[team] / max(vote.sum(), 1e-6)), 3
        )
