"""The executable footage → perception → tracking → state → tactics → Jev pipeline."""

from __future__ import annotations
import hashlib
import json
import os
import time as clock
from pathlib import Path
import cv2
import numpy as np
from .camera import Camera, transform
from .perception import SoccerModels, Detection, TeamClassifier, kit_feature, ROOT
from .tracking import PlayerTracker, BallTracker
from .state import GameState
from .jev import JevJudge, JevUnavailable

PIPELINE_VERSION = "neural-soccer-v2"


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(
    path: Path,
    *,
    models=None,
    duration_limit=30.0,
    sample_fps=5.0,
    use_jev=True,
    home_attacks_right=True,
    progress=None,
    cancelled=None,
    output: Path | None = None,
):
    start = clock.monotonic()
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not capture.isOpened() or fps <= 0 or count <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise ValueError("Unsupported or unreadable video")
    if count / fps > 60.1:
        capture.release()
        raise ValueError("Videos must be 60 seconds or shorter")
    if width * height > 3840 * 2160:
        capture.release()
        raise ValueError("Maximum input resolution is 4K")
    duration = min(count / fps, duration_limit)
    sample_fps = min(5.0, max(1.0, sample_fps))
    digest = file_hash(path)
    cache_dir = ROOT / ".local/perception" / f"{PIPELINE_VERSION}-{digest[:16]}-{sample_fps:g}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    trackers = PlayerTracker()
    ball_tracker = BallTracker()
    camera = Camera()
    teams = TeamClassifier()
    state = GameState(home_attacks_right)
    judge = JevJudge(ROOT / ".local") if use_jev else None
    frames = []
    judgments = []
    judge_count = 0
    last_judge = -10.0
    last_phase = None
    max_judgments = int(os.getenv("JEV_MAX_CALLS_PER_JOB", "12"))
    sample_count = int(np.ceil(duration * sample_fps))
    try:
        for index in range(sample_count):
            if cancelled and cancelled():
                raise InterruptedError("Analysis cancelled")
            timestamp = round(index / sample_fps, 4)
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(timestamp * fps))
            ok, image = capture.read()
            if not ok:
                break
            cache_file = cache_dir / f"{index:05}.json"
            if cache_file.exists():
                raw = json.loads(cache_file.read_text())
                detections = [Detection(**d) for d in raw["players"]]
                balls = [Detection(**d) for d in raw["balls"]]
                keypoints = np.array(raw["keypoints"])
            else:
                if models is None:
                    models = SoccerModels(device=os.getenv("PITCHSTATE_DEVICE", "cpu"))
                detections, balls, keypoints = models.detect(image, ball_tracker.point, index)
                raw = {
                    "players": [d.__dict__ for d in detections],
                    "balls": [d.__dict__ for d in balls],
                    "keypoints": keypoints.tolist(),
                }
                cache_file.write_text(json.dumps(raw))
            matrix, calibration, motion = camera.update(image, keypoints, timestamp)
            if calibration["cut"]:
                trackers.reset()
                ball_tracker.reset()
            tracks = trackers.update(image, detections, timestamp, motion)
            if teams.centers is None:
                teams.fit(
                    [
                        kit_feature(image, t.box)
                        for t in tracks
                        if t.kind == "player" and t.confidence > 0.55
                    ]
                )
            players = []
            for track in tracks:
                center = [float((track.box[0] + track.box[2]) / 2), float(track.box[3])]
                projected = transform([center], matrix)[0] if matrix is not None else None
                if projected is not None and not (
                    -3 <= projected[0] <= 108 and -3 <= projected[1] <= 71
                ):
                    continue
                team, team_confidence = (
                    teams.classify(track.id, track.feature)
                    if track.kind != "referee"
                    else ("unknown", 0.0)
                )
                point = (
                    projected / [1.05, 0.68]
                    if projected is not None
                    else np.array(center) / [width, height] * 100
                )
                players.append(
                    {
                        "id": track.id,
                        "team": team,
                        "teamConfidence": team_confidence,
                        "role": track.kind,
                        "confidence": round(track.confidence, 4),
                        "x": round(float(point[0]), 3),
                        "y": round(float(point[1]), 3),
                        "image": {
                            "x": round(center[0] / width * 100, 3),
                            "y": round(center[1] / height * 100, 3),
                        },
                        "box": [round(float(v), 2) for v in track.box],
                        "status": "observed",
                    }
                )
            ball_obs = ball_tracker.update(balls, timestamp, width, motion)
            ball = None
            if ball_obs is not None:
                p = ball_obs["point"]
                projected = transform([p], matrix)[0] if matrix is not None else None
                if projected is None or (-5 <= projected[0] <= 110 and -5 <= projected[1] <= 73):
                    point = (
                        projected / [1.05, 0.68]
                        if projected is not None
                        else p / [width, height] * 100
                    )
                    ball = {
                        "x": round(float(point[0]), 3),
                        "y": round(float(point[1]), 3),
                        "image": {
                            "x": round(float(p[0]) / width * 100, 3),
                            "y": round(float(p[1]) / height * 100, 3),
                        },
                        "confidence": round(ball_obs["confidence"], 4),
                        "status": ball_obs["status"],
                    }
            frame = {
                "time": timestamp,
                "players": players,
                "ball": ball,
                "calibration": calibration,
                "coordinateSpace": "pitch" if matrix is not None else "image",
            }
            state.update(frame)
            frames.append(frame)
            if (
                judge
                and judge_count < max_judgments
                and (
                    timestamp - last_judge >= 2
                    or (frame["state"]["phase"] != last_phase and timestamp - last_judge >= 1)
                )
            ):
                # A decision is still useful with partial evidence: insufficient_evidence is an explicit output.
                if len(players) >= 4:
                    if cancelled and cancelled():
                        raise InterruptedError("Analysis cancelled")
                    try:
                        judgment = judge.judge(state.for_judge(frame))
                        judgment["time"] = timestamp
                        judgments.append(judgment)
                    except JevUnavailable as error:
                        judgments.append(
                            {"time": timestamp, "source": "unavailable", "reason": str(error)}
                        )
                    judge_count += 1
                    last_judge = timestamp
                    last_phase = frame["state"]["phase"]
            if progress:
                progress(
                    {
                        "stage": "perception" if index < sample_count - 1 else "finalizing",
                        "progress": round((index + 1) / sample_count * 100),
                        "time": timestamp,
                        "players": len(players),
                        "ball": bool(ball),
                        "calibrated": calibration["valid"],
                        "judgments": len(judgments),
                    }
                )
    finally:
        capture.release()
    if not frames:
        raise ValueError("Video contains no decodable frames")
    total = len(frames)
    quality = {
        "frames": total,
        "playerObservations": sum(len(f["players"]) for f in frames),
        "uniqueTracks": len({p["id"] for f in frames for p in f["players"]}),
        "ballObservedFraction": round(
            sum(bool(f["ball"] and f["ball"]["status"] == "observed") for f in frames) / total, 3
        ),
        "ballPredictedFraction": round(
            sum(bool(f["ball"] and f["ball"]["status"] == "predicted") for f in frames) / total, 3
        ),
        "calibratedFraction": round(sum(f["calibration"]["valid"] for f in frames) / total, 3),
        "possessionKnownFraction": round(
            sum(f["state"]["possession"] != "unknown" for f in frames) / total, 3
        ),
        "processingSeconds": round(clock.monotonic() - start, 2),
        "jevResponses": sum(j["source"] == "jev" for j in judgments),
        "shots": camera.shot + 1,
    }
    result = {
        "schemaVersion": 2,
        "pipelineVersion": PIPELINE_VERSION,
        "source": "pipeline",
        "name": path.stem,
        "duration": duration,
        "sampleFps": sample_fps,
        "video": {"width": width, "height": height, "fps": fps, "sha256": digest},
        "frames": frames,
        "events": state.events,
        "judgments": judgments,
        "quality": quality,
        "metadata": {
            "perception": "Soccer-trained YOLOv8 player, ball, and pitch models",
            "tracking": "Two-stage Hungarian motion/appearance association; ball Kalman filter",
            "calibration": "Neural 32-landmark RANSAC homography with optical-flow propagation",
            "teams": "Unsupervised torso appearance; dark cluster is Team A",
            "pitchDimensionsMeters": [105, 68],
            "homeAttacksRight": home_attacks_right,
            "forecastHorizonSeconds": 3,
            "probabilityInterpretation": "Jev model judgments, not empirically calibrated soccer forecasts",
            "limitations": [
                "Off-camera players are unknown",
                "Track IDs are not player names or jersey numbers",
                "Projection assumes ball is on the ground",
                "Attack direction is configured",
                "Pitch dimensions are assumed",
            ],
        },
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, allow_nan=False))
        temporary.replace(output)
    return result
