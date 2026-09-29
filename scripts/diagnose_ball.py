import os
from pathlib import Path

os.environ["YOLO_CONFIG_DIR"] = str(Path(".local/ultralytics").resolve())
import cv2
import torch
from ultralytics import YOLO

torch.set_num_threads(4)
model = YOLO("models/football-ball-detection.pt")
cap = cv2.VideoCapture("data/2e57b9_0.mp4")
for time in [4.4, 5.2, 6.0, 6.8, 10.4, 11.4]:
    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    ok, image = cap.read()
    if not ok:
        continue
    h, w = image.shape[:2]
    candidates = []
    for y in (0, h // 2 - 80):
        for x in (0, w // 2 - 80):
            crop = image[y : min(h, y + h // 2 + 80), x : min(w, x + w // 2 + 80)]
            result = model.predict(
                crop, imgsz=960, conf=0.15, device="cpu", verbose=False
            )[0]
            for row in result.boxes.data.cpu().numpy():
                center = (
                    int((row[0] + row[2]) / 2 + x),
                    int((row[1] + row[3]) / 2 + y),
                )
                candidates.append((center, round(float(row[4]), 3)))
                cv2.circle(image, center, 20, (0, 255, 255), 2)
                cv2.putText(
                    image,
                    str(round(float(row[4]), 2)),
                    (center[0] + 20, center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2,
                )
    cv2.imwrite(f".local/ball-slices-{time}.jpg", image)
    print(time, candidates, flush=True)
cap.release()
