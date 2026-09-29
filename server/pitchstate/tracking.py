"""Camera-compensated two-stage association with motion prediction and torso appearance."""

from dataclasses import dataclass
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from .perception import Detection, kit_feature


def iou(a, b):
    x1, y1 = np.maximum(a[:2], b[:2])
    x2, y2 = np.minimum(a[2:], b[2:])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)

    def area(r):
        return max(0, r[2] - r[0]) * max(0, r[3] - r[1])

    return intersection / max(1, area(a) + area(b) - intersection)


@dataclass
class Track:
    id: int
    box: np.ndarray
    velocity: np.ndarray
    feature: np.ndarray | None
    confidence: float
    kind: str
    seen: float
    updated: float
    hits: int = 1


class PlayerTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def reset(self):
        # IDs never repeat across shots.
        self.tracks.clear()

    def update(self, image, detections: list[Detection], time: float, motion=None):
        self.tracks = {k: t for k, t in self.tracks.items() if time - t.seen <= 1.2}
        features = [kit_feature(image, d.box) for d in detections]
        for track in self.tracks.values():
            if motion is not None:
                points = np.array([track.box[:2], track.box[2:]], dtype=np.float32).reshape(
                    -1, 1, 2
                )
                track.box = cv2.perspectiveTransform(points, motion).reshape(-1)
            dt = time - track.updated
            track.box += track.velocity * dt
            track.updated = time
        unmatched_tracks = set(self.tracks)
        unmatched_detections = set(range(len(detections)))
        matches = []
        # Strong detections establish matches; weak observations only rescue existing tracks.
        for high in (True, False):
            tids = list(unmatched_tracks)
            dids = [i for i in unmatched_detections if (detections[i].confidence >= 0.5) == high]
            if not tids or not dids:
                continue
            cost = np.full((len(tids), len(dids)), 1e6)
            for r, tid in enumerate(tids):
                track = self.tracks[tid]
                for c, idx in enumerate(dids):
                    detection = detections[idx]
                    box = np.array(detection.box)
                    if (track.kind == "referee") != (detection.kind == "referee"):
                        continue
                    scale = max(20, track.box[3] - track.box[1])
                    delta = (
                        np.linalg.norm((track.box[:2] + track.box[2:] - box[:2] - box[2:]) / 2)
                        / scale
                    )
                    appearance = (
                        np.linalg.norm(track.feature - features[idx])
                        if track.feature is not None and features[idx] is not None
                        else 0
                    )
                    if delta > 2.2 or appearance > 0.48:
                        continue
                    cost[r, c] = (
                        0.5 * (1 - iou(track.box, box))
                        + 0.3 * min(delta / 2, 1)
                        + 0.2 * min(appearance / 0.4, 1)
                    )
            rows, cols = linear_sum_assignment(cost)
            for r, c in zip(rows, cols):
                if cost[r, c] > 0.78:
                    continue
                tid, idx = tids[r], dids[c]
                matches.append((tid, idx))
                unmatched_tracks.remove(tid)
                unmatched_detections.remove(idx)
        observed = []
        for tid, idx in matches:
            track = self.tracks[tid]
            d = detections[idx]
            box = np.array(d.box)
            dt = max(0.05, time - track.seen)
            correction = (box - track.box) / dt
            track.velocity = 0.55 * track.velocity + 0.45 * correction
            track.box = box
            track.seen = time
            track.confidence = d.confidence
            track.hits += 1
            if features[idx] is not None:
                track.feature = (
                    features[idx]
                    if track.feature is None
                    else 0.9 * track.feature + 0.1 * features[idx]
                )
            observed.append(track)
        for idx in unmatched_detections:
            d = detections[idx]
            if d.confidence < 0.4:
                continue
            track = Track(
                self.next_id,
                np.array(d.box),
                np.zeros(4),
                features[idx],
                d.confidence,
                d.kind,
                time,
                time,
            )
            self.tracks[track.id] = track
            self.next_id += 1
            observed.append(track)
        return observed


class BallTracker:
    def __init__(self):
        self.filter = None
        self.last_seen = -10.0
        self.last_time = None
        self.confidence = 0
        self.point = None

    def reset(self):
        self.__init__()

    def update(self, candidates: list[Detection], time, width, motion=None):
        dt = max(0.01, time - (self.last_time if self.last_time is not None else time - 0.2))
        self.last_time = time
        prediction = None
        if self.filter is not None:
            if motion is not None:
                p = self.filter.statePost[:2].reshape(1, 1, 2)
                self.filter.statePost[:2] = cv2.perspectiveTransform(
                    p, motion.astype(np.float32)
                ).reshape(2, 1)
            self.filter.transitionMatrix = np.array(
                [[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
            )
            prediction = self.filter.predict()[:2, 0]
        if prediction is not None and time - self.last_seen <= 0.6:
            gate = max(50, width * 0.22 * dt)
            ranked = sorted(
                candidates,
                key=lambda d: np.linalg.norm(d.center - prediction) / gate - 0.5 * d.confidence,
            )
            chosen = next((d for d in ranked if np.linalg.norm(d.center - prediction) < gate), None)
        else:
            chosen = max(candidates, key=lambda d: d.confidence, default=None)
        if chosen is None and candidates:
            strongest = max(candidates, key=lambda d: d.confidence)
            if strongest.confidence >= 0.7 and (
                prediction is None or np.linalg.norm(strongest.center - prediction) < width * 0.25
            ):
                chosen = strongest
                self.filter = None  # A verified global reacquisition resets stale velocity.
        if chosen is not None:
            if self.filter is None or time - self.last_seen > 0.6:
                self.filter = cv2.KalmanFilter(4, 2)
                self.filter.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
                self.filter.processNoiseCov = np.diag([20, 20, 200, 200]).astype(np.float32)
                self.filter.measurementNoiseCov = np.eye(2, dtype=np.float32) * 9
                self.filter.errorCovPost = np.eye(4, dtype=np.float32) * 100
                self.filter.statePost = np.array([*chosen.center, 0, 0], np.float32).reshape(4, 1)
                point = chosen.center
            else:
                point = self.filter.correct(chosen.center.astype(np.float32).reshape(2, 1))[:2, 0]
            self.last_seen = time
            self.confidence = chosen.confidence
            self.point = point.copy()
            return {
                "point": point,
                "confidence": chosen.confidence,
                "status": "observed",
                "box": chosen.box,
            }
        if prediction is not None and time - self.last_seen <= 0.4:
            self.point = prediction.copy()
            return {
                "point": prediction,
                "confidence": self.confidence * 0.5,
                "status": "predicted",
                "box": None,
            }
        self.point = None
        return None
