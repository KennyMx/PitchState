"""Render the real replay JSON and source excerpt into a reproducible README demo."""

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
analysis = json.loads((ROOT / ".local/real-analysis.json").read_text())
source = cv2.VideoCapture(str(ROOT / "data/2e57b9_0.mp4"))
fps = source.get(cv2.CAP_PROP_FPS)
writer = cv2.VideoWriter(
    str(ROOT / ".local/readme-demo.avi"),
    cv2.VideoWriter_fourcc(*"MJPG"),
    fps,
    (1120, 640),
)
font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
fonts = {s: ImageFont.truetype(font_path, s) for s in (11, 13, 15, 18, 24, 32)}
frames = analysis["frames"]
for n in range(round(analysis["duration"] * fps)):
    ok, video = source.read()
    if not ok:
        break
    t = n / fps
    index = min(int(t * analysis["sampleFps"]), len(frames) - 1)
    a, b = frames[index], frames[min(index + 1, len(frames) - 1)]
    ratio = max(0, min(1, (t - a["time"]) / max(0.001, b["time"] - a["time"])))
    canvas = Image.new("RGB", (1120, 640), "#0d1711")
    d = ImageDraw.Draw(canvas)

    def text(x, y, value, size=15, color="#e6eedf", draw=d):
        draw.text((x, y), str(value), font=fonts[size], fill=color)

    text(26, 18, "PitchState", 32, "#d0f895")
    text(220, 33, "SEE THE GAME BENEATH THE GAME", 13, "#a5b59d")
    text(877, 32, "REAL FOOTAGE  /  LEVEL 2", 13, "#d0f895")
    text(26, 85, "ORIGINAL FOOTAGE + TRACKING", 13, "#a5b59d")
    text(773, 85, "PITCH RECONSTRUCTION", 13, "#a5b59d")
    canvas.paste(
        Image.fromarray(cv2.cvtColor(cv2.resize(video, (720, 405)), cv2.COLOR_BGR2RGB)),
        (26, 112),
    )
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(
        (770, 112, 1093, 355), radius=10, fill="#1b3528", outline="#344c37"
    )
    d.rectangle((789, 129, 1074, 338), outline="#6b826b", width=1)
    d.line((931, 129, 931, 338), fill="#6b826b")
    d.ellipse((901, 203, 961, 263), outline="#6b826b")
    d.rectangle((789, 184, 825, 282), outline="#6b826b")
    d.rectangle((1038, 184, 1074, 282), outline="#6b826b")
    for p in a["players"]:
        q = next((q for q in b["players"] if q["id"] == p["id"]), p)
        color = (
            "#d0f895"
            if p["team"] == "home"
            else "#a6baff"
            if p["team"] == "away"
            else "#aab5a8"
        )
        x = p["x"] + (q["x"] - p["x"]) * ratio
        y = p["y"] + (q["y"] - p["y"]) * ratio
        px, py = 789 + x * 2.85, 129 + y * 2.09
        if 782 < px < 1081 and 122 < py < 345:
            d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color)
        box = [
            v + (q.get("box", p["box"])[i] - v) * ratio for i, v in enumerate(p["box"])
        ]
        x1, y1, x2, y2 = [
            26 + box[0] / analysis["video"]["width"] * 720,
            112 + box[1] / analysis["video"]["height"] * 405,
            26 + box[2] / analysis["video"]["width"] * 720,
            112 + box[3] / analysis["video"]["height"] * 405,
        ]
        d.rectangle((x1, y1, x2, y2), outline=color, width=1)
        d.text(
            (x1, y1 - 12),
            str(p["id"]),
            font=fonts[11],
            fill=color,
            stroke_width=1,
            stroke_fill="#172219",
        )
    ball = a.get("ball")
    if ball:
        image = ball["image"]
        next_ball = b.get("ball") or ball
        bx = image["x"] + (next_ball["image"]["x"] - image["x"]) * ratio
        by = image["y"] + (next_ball["image"]["y"] - image["y"]) * ratio
        vx, vy = 26 + bx * 7.2, 112 + by * 4.05
        d.ellipse((vx - 7, vy - 7, vx + 7, vy + 7), outline="#fff277", width=2)
        px, py = 789 + ball["x"] * 2.85, 129 + ball["y"] * 2.09
        d.ellipse((px - 3, py - 3, px + 3, py + 3), fill="#fff277")
    judgment = next(
        (j for j in reversed(analysis["judgments"]) if j["time"] <= t), None
    )
    control = a["state"]["ballControl"]
    text(774, 375, "NOW", 11, "#9bae91")
    text(774, 394, control["label"], 18)
    text(774, 435, "JEV / MOST LIKELY NEXT", 11, "#9bae91")
    label = "Decision unavailable"
    probability = 0
    if (
        judgment
        and judgment["source"] == "jev"
        and judgment.get("controlEpoch") == control["epoch"]
        and t < judgment["validUntil"]
    ):
        choice = max(
            judgment["nextDecision"]["probabilities"],
            key=judgment["nextDecision"]["probabilities"].get,
        )
        label = next(c["label"] for c in judgment["candidates"] if c["id"] == choice)
        probability = judgment["nextDecision"]["probabilities"][choice]
    text(774, 456, label, 18, "#d0f895")
    d.rounded_rectangle((774, 487, 1090, 491), radius=2, fill="#2f4130")
    if probability > 0:
        d.rectangle((774, 487, 774 + 316 * probability, 491), fill="#d0f895")
    text(
        774,
        502,
        f"{probability:.0%} probability"
        if probability
        else "Evidence remains explicit",
        13,
        "#a5b59d",
    )
    text(
        26,
        539,
        "PERCEPTION  →  STATE  →  TACTICS  →  JEV  →  SPECIFIC DECISIONS",
        13,
        "#9bae91",
    )
    d.rounded_rectangle((26, 577, 1093, 581), radius=2, fill="#2f4130")
    d.rectangle((26, 577, 26 + 1067 * t / analysis["duration"], 581), fill="#d0f895")
    text(
        26,
        599,
        f"{t:04.1f}s / {analysis['duration']:.0f}s   ·   {fps:g} FPS replay   ·   5 Hz analysis",
        13,
    )
    text(
        618,
        601,
        "Track IDs, not jersey numbers · Forecasts are model estimates",
        11,
        "#9bae91",
    )
    writer.write(cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR))
writer.release()
source.release()
