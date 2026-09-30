from server.pitchstate.decisions import BallControl, action_candidates


def frame(t, x, shot=0):
    return {
        "time": t,
        "calibration": {"valid": True, "shot": shot},
        "players": [
            {"id": 1, "team": "home", "role": "player", "x": 20, "y": 50},
            {"id": 2, "team": "home", "role": "player", "x": 40, "y": 50},
            {"id": 3, "team": "away", "role": "player", "x": 50, "y": 60},
        ],
        "ball": {"x": x, "y": 50, "confidence": 0.9},
        "state": {"homeAttacksRight": True, "context": {}},
    }


def test_release_invalidates_pass_and_forecasts_reception():
    control = BallControl()
    control.update(frame(0, 20))
    owned = control.update(frame(0.2, 20.2))
    assert owned["actorId"] == 1
    released = frame(0.4, 27)
    released["state"]["ballControl"] = control.update(released)
    assert released["state"]["ballControl"]["phase"] == "released"
    assert released["state"]["ballControl"]["epoch"] != owned["epoch"]
    options = action_candidates(released)
    assert not any(c["kind"] in ("pass", "carry", "cross", "shot") for c in options)
    assert any(c["targetId"] == 2 for c in options)
    control.update(frame(0.6, 35))
    control.update(frame(0.8, 39.8))
    control.update(frame(1, 40))
    received = control.update(frame(1.2, 40.1))
    assert received["actorId"] == 2 and received["phase"] == "reception"


def test_cut_and_missing_ball_never_preserve_control():
    control = BallControl()
    control.update(frame(0, 20))
    control.update(frame(0.2, 20))
    cut = frame(0.4, 20, shot=1)
    cut["ball"] = None
    result = control.update(cut)
    assert (
        result["phase"] == "unknown" and result["actorId"] is None and result["lastActorId"] is None
    )


def test_pass_candidates_reference_visible_teammates_only():
    control = BallControl()
    control.update(frame(0, 20))
    current = frame(0.2, 20)
    current["state"]["ballControl"] = control.update(current)
    options = action_candidates(current)
    named = [c for c in options if c["kind"] == "pass" and c["targetId"] is not None]
    assert len(named) == 1 and named[0]["actorId"] == 1 and named[0]["targetId"] == 2
    assert len({c["id"] for c in options}) == len(options)
