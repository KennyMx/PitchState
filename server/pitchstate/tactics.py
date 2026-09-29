"""Explicit soccer geometry and maintained domain context for interpretation."""

import hashlib
from pathlib import Path
import numpy as np

REFERENCE = Path(__file__).resolve().parents[2] / "docs/TACTICAL_REFERENCE.md"


def knowledge():
    source = REFERENCE.read_text()
    runtime = source.split("<!-- runtime:start -->")[1].split("<!-- runtime:end -->")[0].strip()
    return {
        "version": "soccer-context-v1",
        "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "guidance": runtime,
    }


def contextual_features(frame, history, home_right):
    state, ball = frame["state"], frame.get("ball")
    valid = frame["calibration"]["valid"]
    result = {
        "attackingTeam": None,
        "contextSource": "unavailable",
        "contextAgeSeconds": None,
        "canReason": False,
    }
    if not valid or not ball or ball.get("confidence", 0) < 0.12:
        result["abstentionReason"] = "missing_geometry" if not valid else "missing_ball"
        return result
    players = [
        p for p in frame["players"] if p["team"] in ("home", "away") and p.get("role") != "referee"
    ]
    team = state["possession"] if state["possession"] != "unknown" else None
    source, age = "confirmed_possession", 0
    point = np.array([ball["x"] * 1.05, ball["y"] * 0.68])
    ranked = sorted(
        [
            (float(np.linalg.norm(np.array([p["x"] * 1.05, p["y"] * 0.68]) - point)), p["id"], p)
            for p in players
        ]
    )
    if (
        not team
        and ranked
        and ranked[0][0] <= 4
        and (len(ranked) < 2 or ranked[1][0] - ranked[0][0] > 1)
    ):
        team, source = ranked[0][2]["team"], "nearby_player_hypothesis"
    if not team:
        for old in reversed(list(history)):
            age = frame["time"] - old["time"]
            if age > 2 or old["calibration"]["shot"] != frame["calibration"]["shot"]:
                break
            if old.get("state", {}).get("possession") in ("home", "away"):
                team, source = old["state"]["possession"], "recent_team_ball_in_transit"
                break
    if not team:
        result["abstentionReason"] = "attacking_team_unresolved"
        return result
    direction = 1 if (team == "home") == home_right else -1
    ax = ball["x"] * 1.05 if direction == 1 else 105 - ball["x"] * 1.05
    y = ball["y"] * 0.68
    attackers = [p for p in players if p["team"] == team]
    defenders = [p for p in players if p["team"] != team]

    def oriented(p):
        return p["x"] * 1.05 if direction == 1 else 105 - p["x"] * 1.05

    box = [
        p
        for p in attackers
        if oriented(p) >= 88.5 and 13.84 <= p["y"] * 0.68 <= 54.16 and p["id"] != state["carrierId"]
    ]
    prior = next(
        (
            f
            for f in reversed(list(history))
            if 0.6 <= frame["time"] - f["time"] <= 1.2
            and f["calibration"]["shot"] == frame["calibration"]["shot"]
            and f["calibration"]["valid"]
        ),
        None,
    )
    entering = []
    if prior:
        old = {p["id"]: p for p in prior["players"]}
        entering = [
            p["id"] for p in box if p["id"] in old and oriented(p) - oriented(old[p["id"]]) > 1
        ]
    outlets = []
    for p in attackers:
        end = np.array([p["x"] * 1.05, p["y"] * 0.68])
        delta = end - point
        length = float(np.linalg.norm(delta))
        if p["id"] == state["carrierId"] or not 3 < length < 35:
            continue
        blocked = False
        for d in defenders:
            dp = np.array([d["x"] * 1.05, d["y"] * 0.68]) - point
            fraction = float(np.dot(dp, delta) / max(length * length, 0.01))
            if 0 < fraction < 1 and np.linalg.norm(dp - fraction * delta) < 1.8:
                blocked = True
        if not blocked:
            outlets.append(p["id"])
    wide = min(y, 68 - y) < 17
    result.update(
        attackingTeam=team,
        contextSource=source,
        contextAgeSeconds=round(age, 2),
        canReason=True,
        distanceToGoalLineMeters=round(105 - ax, 2),
        distanceToTouchlineMeters=round(min(y, 68 - y), 2),
        wide=wide,
        byline=bool(ax > 93),
        crossingTerritory=bool(wide and ax > 70),
        boxTargetIds=[p["id"] for p in box],
        boxEnteringRunIds=entering,
        cutbackTargetIds=[p["id"] for p in box if oriented(p) < ax - 2],
        clearPassingLaneIds=outlets,
        centralShootingZone=bool(ax > 80 and abs(y - 34) < 14),
        ballInTransit=bool(state["carrierId"] is None),
        crossingSupport=round(
            float(np.clip((ax - 65) / 30, 0, 1)) * min(1, len(box) / 2) if wide else 0, 3
        ),
    )
    return result
