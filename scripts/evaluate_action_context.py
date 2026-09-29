"""Opt-in paid sensitivity check; synthetic soccer scenarios, never an accuracy benchmark."""

import json
from pathlib import Path

from dotenv import load_dotenv

from server.pitchstate.jev import JevJudge
from server.pitchstate.tactics import contextual_features, knowledge


def scenario(x, box=True, missing=False):
    players = [
        {"id": 1, "x": x, "y": 12, "team": "home", "role": "player"},
        {"id": 2, "x": 90 if box else 50, "y": 48, "team": "home", "role": "player"},
        {"id": 3, "x": 94 if box else 55, "y": 58, "team": "home", "role": "player"},
        {"id": 4, "x": 87, "y": 35, "team": "away", "role": "player"},
    ]
    frame = {
        "time": 2,
        "players": players,
        "ball": None
        if missing
        else {"x": x, "y": 12, "confidence": 0.9, "status": "observed"},
        "calibration": {"valid": True, "shot": 0},
        "state": {
            "possession": "unknown" if missing else "home",
            "carrierId": None if missing else 1,
        },
    }
    frame["state"]["context"] = contextual_features(frame, [], True)
    return {
        "sport": "association football",
        "forecastHorizonSeconds": 3,
        "tacticalReference": knowledge(),
        "current": frame["state"],
        "ball": frame["ball"],
        "players": players,
        "calibration": frame["calibration"],
        "history": [],
        "syntheticSensitivityScenario": True,
    }


if __name__ == "__main__":
    load_dotenv(".env.local")
    judge = JevJudge(Path(".local"))
    rows = []
    for name, state in [
        ("wide_approach", scenario(67)),
        ("byline_with_targets", scenario(95)),
        ("byline_empty_box", scenario(95, False)),
        ("missing_ball", scenario(50, False, True)),
    ]:
        result = judge.judge(state)
        rows.append(
            {
                "scenario": name,
                "nextAction": result["nextAction"],
                "source": result["source"],
                "cached": result["cached"],
            }
        )
    out = Path("reports/action-context-sensitivity.json")
    out.write_text(
        json.dumps(
            {
                "kind": "synthetic sensitivity, not predictive accuracy",
                "model": "jev-1.13.0",
                "referenceHash": knowledge()["sha256"],
                "results": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(rows, indent=2))
