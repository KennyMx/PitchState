"""Render locally acquired footage with actual inferred observations for visual QA."""

import json
from pathlib import Path

import cv2
import numpy as np

analysis = json.loads(Path(".local/real-analysis.json").read_text())
cap = cv2.VideoCapture("data/2e57b9_0.mp4")
images = []
for time in [0, 2, 4, 6, 8, 10]:
    f = min(analysis["frames"], key=lambda f: abs(f["time"] - time))
    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    ok, image = cap.read()
    if not ok:
        continue
    for p in f["players"]:
        x1, y1, x2, y2 = map(int, p["box"])
        color = (
            (120, 230, 170)
            if p["team"] == "home"
            else (245, 170, 125)
            if p["team"] == "away"
            else (160, 160, 160)
        )
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            image, str(p["id"]), (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1
        )
    if f["ball"]:
        b = f["ball"]
        point = (
            int(b["image"]["x"] / 100 * image.shape[1]),
            int(b["image"]["y"] / 100 * image.shape[0]),
        )
        cv2.circle(image, point, 20, (0, 255, 255), 3)
    cv2.putText(
        image,
        f"t={time}s | ball={f['ball']['status'] if f['ball'] else 'missing'} | possession={f['state']['possession']}",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )
    cv2.imwrite(f".local/evaluation-{time}.jpg", image)
    images.append(cv2.resize(image, (960, 540)))
cap.release()
cv2.imwrite(
    ".local/evaluation-contact.jpg",
    np.vstack([np.hstack(images[i : i + 2]) for i in range(0, len(images), 2)]),
)
print(json.dumps(analysis["quality"], indent=2))
