import os
from pathlib import Path

os.environ["YOLO_CONFIG_DIR"] = str(Path(".local/ultralytics").resolve())
import cv2
import torch
from ultralytics import YOLO

cap = cv2.VideoCapture("data/2e57b9_0.mp4")
ok, frame = cap.read()
cap.release()
assert ok
cv2.imwrite(".local/real-frame.jpg", frame)
print("frame", frame.shape, "mps", torch.backends.mps.is_available(), flush=True)
for name in ["player", "ball", "pitch"]:
    model = YOLO(f"models/football-{name}-detection.pt")
    result = model.predict(
        frame,
        imgsz=1280 if name == "ball" else 640,
        conf=0.15,
        device="cpu",
        verbose=False,
    )[0]
    print(name, model.names, "speed", result.speed, flush=True)
    if result.keypoints is not None:
        print(
            "keypoints",
            result.keypoints.data.cpu().numpy().round(2).tolist(),
            flush=True,
        )
    else:
        print("boxes", result.boxes.data.cpu().numpy().round(3).tolist(), flush=True)
    cv2.imwrite(f".local/{name}-detections.jpg", result.plot())
