"""Automatic per-frame field calibration, robust camera motion and shot-change invalidation."""

import cv2
import numpy as np

# Indices follow the published 32-landmark Roboflow soccer model. Coordinates are
# standard 105x68m geometry, not the tutorial's illustrative 120x70m drawing.
L, W = 105.0, 68.0
PITCH_POINTS = np.array(
    [
        (0, 0),
        (0, 13.84),
        (0, 24.84),
        (0, 43.16),
        (0, 54.16),
        (0, 68),
        (5.5, 24.84),
        (5.5, 43.16),
        (11, 34),
        (16.5, 13.84),
        (16.5, 24.84),
        (16.5, 43.16),
        (16.5, 54.16),
        (52.5, 0),
        (52.5, 24.85),
        (52.5, 43.15),
        (52.5, 68),
        (88.5, 13.84),
        (88.5, 24.84),
        (88.5, 43.16),
        (88.5, 54.16),
        (94, 34),
        (99.5, 24.84),
        (99.5, 43.16),
        (105, 0),
        (105, 13.84),
        (105, 24.84),
        (105, 43.16),
        (105, 54.16),
        (105, 68),
        (43.35, 34),
        (61.65, 34),
    ],
    dtype=np.float32,
)


def transform(points, matrix):
    if matrix is None:
        return None
    return cv2.perspectiveTransform(
        np.array(points, dtype=np.float32).reshape(-1, 1, 2), matrix
    ).reshape(-1, 2)


def fit_pitch(keypoints, width, height):
    if len(keypoints) != 32:
        return None, {"valid": False, "reason": "missing_landmarks"}
    mask = (
        (keypoints[:, 2] > 0.65)
        & (keypoints[:, 0] > 1)
        & (keypoints[:, 0] < width - 1)
        & (keypoints[:, 1] > 1)
        & (keypoints[:, 1] < height - 1)
    )
    source = keypoints[mask, :2].astype(np.float32)
    target = PITCH_POINTS[mask]
    if len(source) < 5 or cv2.contourArea(cv2.convexHull(source)) < width * height * 0.008:
        return None, {
            "valid": False,
            "reason": "insufficient_landmark_spread",
            "landmarks": len(source),
        }
    matrix, inliers = cv2.findHomography(source, target, cv2.RANSAC, 2.0)
    if matrix is None or inliers is None:
        return None, {"valid": False, "reason": "homography_failed"}
    chosen = inliers.ravel().astype(bool)
    residual = np.linalg.norm(transform(source, matrix) - target, axis=1)
    error = float(np.median(residual[chosen]))
    valid = (
        int(chosen.sum()) >= 5
        and chosen.mean() >= 0.55
        and error < 1.5
        and np.isfinite(matrix).all()
    )
    quality = {
        "valid": bool(valid),
        "landmarks": int(len(source)),
        "inliers": int(chosen.sum()),
        "reprojectionErrorMeters": round(error, 3),
        "confidence": round(float(chosen.mean() * np.exp(-error / 2)), 3),
        "method": "neural_landmarks_ransac",
    }
    return (matrix if valid else None), quality


class Camera:
    def __init__(self):
        self.gray = None
        self.hist = None
        self.matrix = None
        self.last_calibrated = -10.0
        self.shot = 0

    def update(self, image, keypoints, time):
        h, w = image.shape[:2]
        small = cv2.resize(image, (480, 270))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        cut = (
            self.hist is not None
            and cv2.compareHist(self.hist, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.50
        )
        motion = np.eye(3)
        flow_inliers = 0
        if self.gray is not None and not cut:
            points = cv2.goodFeaturesToTrack(
                self.gray, maxCorners=150, qualityLevel=0.02, minDistance=10
            )
            if points is not None and len(points) > 10:
                nxt, status, _ = cv2.calcOpticalFlowPyrLK(self.gray, gray, points, None)
                if nxt is not None:
                    good = status.ravel() == 1
                    if good.sum() >= 10:
                        affine, inliers = cv2.estimateAffinePartial2D(
                            points[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=2
                        )
                        if affine is not None:
                            motion[:2] = affine
                            motion[0, 2] *= w / 480
                            motion[1, 2] *= h / 270
                            flow_inliers = int(inliers.sum())
            # A shot cut may have similar grass colors; near-total flow failure is independent evidence.
            if flow_inliers < 5 and np.mean(cv2.absdiff(self.gray, gray)) > 45:
                cut = True
        if cut:
            self.matrix = None
            self.shot += 1
        matrix, quality = fit_pitch(keypoints, w, h)
        if matrix is not None:
            self.matrix = matrix
            self.last_calibrated = time
        elif (
            self.matrix is not None
            and time - self.last_calibrated < 0.6
            and flow_inliers >= 15
            and not cut
        ):
            self.matrix = self.matrix @ np.linalg.inv(motion)
            quality = {
                "valid": True,
                "confidence": 0.35,
                "method": "flow_propagated",
                "ageSeconds": round(time - self.last_calibrated, 3),
            }
        else:
            self.matrix = None
        self.gray = gray
        self.hist = hist
        quality.update({"shot": self.shot, "cut": bool(cut), "cameraFlowInliers": flow_inliers})
        return self.matrix, quality, motion
