"""Audit completed Level 2 replay contracts; no network or paid model requests."""

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(path):
    replay = json.loads(path.read_text())
    frames = {f["time"]: f for f in replay["frames"]}
    failures = []
    examples = []
    for j in replay["judgments"]:
        if j["source"] != "jev":
            continue
        f = frames[j["time"]]
        control = f["state"]["ballControl"]
        if j.get("controlEpoch") != control["epoch"]:
            failures.append("epoch mismatch")
        if j.get("validUntil", 999) > j["time"] + 1 / replay["sampleFps"] + 0.0001:
            failures.append("expiry exceeds cadence")
        candidates = j.get("candidates", [])
        if control["phase"] in ("released", "in_transit") and any(
            c["kind"] in ("pass", "carry", "cross", "shot") for c in candidates
        ):
            failures.append("new carrier action offered during transit")
        visible = {p["id"] for p in f["players"]}
        if any(
            c.get("targetId") is not None and c["targetId"] not in visible
            for c in candidates
        ):
            failures.append("target not visible")
        if abs(sum(j["nextDecision"]["probabilities"].values()) - 1) > 0.002:
            failures.append("invalid probabilities")
        leading = max(
            j["nextDecision"]["probabilities"],
            key=j["nextDecision"]["probabilities"].get,
        )
        c = next(c for c in candidates if c["id"] == leading)
        if len(examples) < 8 and (
            not examples or examples[-1]["ballPhase"] != control["phase"]
        ):
            examples.append(
                {
                    "time": j["time"],
                    "ballPhase": control["phase"],
                    "next": c["label"],
                    "probability": j["nextDecision"]["probabilities"][leading],
                }
            )
    result = {
        "clip": replay["name"],
        "seconds": replay["duration"],
        "sourceFps": replay["video"]["fps"],
        "analysisHz": replay["sampleFps"],
        "decisionSlots": len(replay["judgments"]),
        "validDecisions": sum(j["source"] == "jev" for j in replay["judgments"]),
        "unavailableDecisions": sum(j["source"] != "jev" for j in replay["judgments"]),
        "ballPhases": dict(
            Counter(f["state"]["ballControl"]["phase"] for f in frames.values())
        ),
        "contractFailures": failures,
        "examples": examples,
        "quality": replay["quality"],
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("analyses", type=Path, nargs="+")
    parser.add_argument(
        "--output", type=Path, default=Path("reports/level2-evaluation.json")
    )
    args = parser.parse_args()
    rows = [audit(p) for p in args.analyses]
    args.output.write_text(
        json.dumps(
            {
                "scope": "Replay contract checks on real development clips, not ground-truth recipient accuracy",
                "runs": rows,
            },
            indent=2,
        )
        + "\n"
    )
    if any(r["contractFailures"] for r in rows):
        raise SystemExit("Replay contract audit failed")
    print(f"{len(rows)} real replay audits passed")
