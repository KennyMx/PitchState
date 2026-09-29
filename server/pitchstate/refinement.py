"""Conservative offline tracklet linking, team consensus and bounded gap reconstruction.

Uses future observations for retrospective reconstruction, never across cuts. No gaps
are labeled observed and ambiguous tracklet links are deliberately left separate.
"""

from copy import deepcopy
from collections import defaultdict
import numpy as np


def compatible(a, b):
    return (a["calibration"]["shot"], a["coordinateSpace"]) == (
        b["calibration"]["shot"],
        b["coordinateSpace"],
    )


def interpolate(a, b, r):
    out = deepcopy(a)
    for key in ("x", "y"):
        out[key] = a[key] + r * (b[key] - a[key])
    if a.get("image") and b.get("image"):
        out["image"] = {k: a["image"][k] + r * (b["image"][k] - a["image"][k]) for k in ("x", "y")}
    if a.get("box") and b.get("box"):
        out["box"] = (np.array(a["box"]) * (1 - r) + np.array(b["box"]) * r).tolist()
    out["status"] = "reconstructed"
    out["confidence"] = min(a["confidence"], b["confidence"]) * 0.7
    return out


def refine(observations):
    frames = deepcopy(observations)
    tracks = defaultdict(list)
    for i, f in enumerate(frames):
        for p in f["players"]:
            tracks[p["id"]].append((i, p))
    links = {}
    used = set()
    for identity, points in sorted(tracks.items(), key=lambda item: item[1][0][0]):
        start, first = points[0]
        candidates = []
        for prior, history in tracks.items():
            end, last = history[-1]
            dt = frames[start]["time"] - frames[end]["time"]
            if prior == identity or prior in used or not 0.0 < dt <= 1.4:
                continue
            if (
                not compatible(frames[start], frames[end])
                or frames[start]["coordinateSpace"] != "pitch"
            ):
                continue
            if (
                first["role"] != last["role"]
                or first["team"] != last["team"]
                or first["team"] == "unknown"
            ):
                continue
            appearance = np.linalg.norm(
                np.array(first.get("_appearance", [])) - np.array(last.get("_appearance", []))
            )
            if not first.get("_appearance") or not last.get("_appearance") or appearance > 0.16:
                continue
            distance = np.linalg.norm(
                (np.array([first["x"], first["y"]]) - [last["x"], last["y"]]) * [1.05, 0.68]
            )
            if distance <= min(8, 2 + 7 * dt):
                candidates.append((distance + appearance * 20, prior))
        candidates.sort()
        if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > 2):
            parent = candidates[0][1]
            links[identity] = links.get(parent, parent)
            used.add(parent)
    tracks = defaultdict(list)
    for i, f in enumerate(frames):
        for p in f["players"]:
            p["id"] = links.get(p["id"], p["id"])
            tracks[p["id"]].append((i, p))
    gaps = 0
    for identity, points in tracks.items():
        votes = defaultdict(float)
        for _, p in points:
            if p["team"] != "unknown":
                votes[p["team"]] += p.get("teamConfidence", 0) * p["confidence"]
        winner = max(votes, key=votes.get) if votes else None
        agreement = votes[winner] / sum(votes.values()) if winner else 0
        for _, p in points:
            if winner and agreement >= 0.8 and p["role"] != "referee":
                p["team"], p["teamConfidence"] = winner, round(agreement, 3)
        for (a, p), (b, q) in zip(points, points[1:]):
            dt = frames[b]["time"] - frames[a]["time"]
            if (
                b > a + 1
                and dt <= 0.8
                and compatible(frames[a], frames[b])
                and frames[a]["coordinateSpace"] == "pitch"
            ):
                speed = (
                    np.linalg.norm((np.array([q["x"], q["y"]]) - [p["x"], p["y"]]) * [1.05, 0.68])
                    / dt
                )
                if speed < 11:
                    for i in range(a + 1, b):
                        if not compatible(frames[a], frames[i]):
                            continue
                        frames[i]["players"].append(
                            interpolate(p, q, (frames[i]["time"] - frames[a]["time"]) / dt)
                        )
                        gaps += 1
        # Symmetric local smoothing only on pitch positions; boxes stay tied to image evidence.
        original = [(i, p["x"], p["y"]) for i, p in points]
        for k, (i, p) in enumerate(points):
            if 0 < k < len(points) - 1:
                left, right = original[k - 1], original[k + 1]
                if i - left[0] == right[0] - i == 1 and compatible(
                    frames[left[0]], frames[right[0]]
                ):
                    x, y = (
                        0.2 * left[1] + 0.6 * p["x"] + 0.2 * right[1],
                        0.2 * left[2] + 0.6 * p["y"] + 0.2 * right[2],
                    )
                    if np.hypot(x - p["x"], y - p["y"]) < 2:
                        p["x"], p["y"] = x, y
    anchors = [
        i for i, f in enumerate(frames) if f.get("ball") and f["ball"]["status"] == "observed"
    ]
    ball_gaps = 0
    for a, b in zip(anchors, anchors[1:]):
        dt = frames[b]["time"] - frames[a]["time"]
        p, q = frames[a]["ball"], frames[b]["ball"]
        if (
            b > a + 1
            and dt <= 0.8
            and compatible(frames[a], frames[b])
            and frames[a]["coordinateSpace"] == "pitch"
        ):
            speed = (
                np.linalg.norm((np.array([q["x"], q["y"]]) - [p["x"], p["y"]]) * [1.05, 0.68]) / dt
            )
            if speed < 40:
                for i in range(a + 1, b):
                    if compatible(frames[a], frames[i]):
                        frames[i]["ball"] = interpolate(
                            p, q, (frames[i]["time"] - frames[a]["time"]) / dt
                        )
                        ball_gaps += 1
    for f in frames:
        for p in f["players"]:
            p.pop("_appearance", None)
    return frames, {
        "linkedTracklets": len(links),
        "reconstructedPlayerSamples": gaps,
        "reconstructedBallSamples": ball_gaps,
        "usesFutureObservations": True,
    }
