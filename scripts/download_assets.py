"""Acquire the publicly linked soccer models and an evaluation clip; never commit weights/video."""

import argparse
import hashlib
import json
from pathlib import Path

import gdown

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", action="store_true")
    parser.add_argument("--footage", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "models/manifest.json").read_text())
    items = []
    if args.models:
        items.extend((ROOT / "models", item) for item in manifest["models"])
    if args.footage:
        items.extend((ROOT / "data", item) for item in manifest["evaluationClips"])
    receipts = {}
    for directory, item in items:
        directory.mkdir(exist_ok=True)
        target = directory / item["file"]
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".part")
            gdown.download(id=item["driveId"], output=str(temporary), quiet=False)
            if not temporary.exists() or temporary.stat().st_size < 10000:
                raise RuntimeError(f"Asset download failed: {item['file']}")
            temporary.replace(target)
        receipts[item["file"]] = {
            "bytes": target.stat().st_size,
            "sha256": hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
            if hasattr(hashlib, "file_digest")
            else hashlib.sha256(target.read_bytes()).hexdigest(),
        }
    output = ROOT / ".local/asset-receipts.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(receipts, indent=2))
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
