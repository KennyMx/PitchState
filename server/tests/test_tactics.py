from server.pitchstate.tactics import contextual_features, knowledge


def situation(x, targets=True, mirrored=False):
    def p(i, x, y, team="home"):
        return dict(id=i, x=100 - x if mirrored else x, y=y, team=team, role="player")

    players = [p(1, x, 12), p(2, 85, 48), p(3, 88, 55)] if targets else [p(1, x, 12), p(2, 40, 48)]
    return {
        "time": 1,
        "players": players,
        "ball": dict(x=100 - x if mirrored else x, y=12, confidence=0.9),
        "calibration": {"valid": True, "shot": 0},
        "state": {"possession": "home", "carrierId": 1},
    }


def test_byline_and_box_arrivals_increase_crossing_support_in_both_directions():
    for mirrored in (False, True):
        early = contextual_features(situation(70, mirrored=mirrored), [], not mirrored)
        late = contextual_features(situation(94, mirrored=mirrored), [], not mirrored)
        empty = contextual_features(
            situation(94, targets=False, mirrored=mirrored), [], not mirrored
        )
        assert late["crossingSupport"] > early["crossingSupport"] > empty["crossingSupport"]
        assert late["byline"] and late["boxTargetIds"]


def test_ball_flight_keeps_bounded_team_context_without_inventing_carrier():
    old = situation(70)
    old["time"] = 0
    current = situation(94)
    current["state"] = {"possession": "unknown", "carrierId": None}
    current["ball"]["y"] = 90
    context = contextual_features(current, [old], True)
    assert context["canReason"] and context["contextSource"] == "recent_team_ball_in_transit"
    assert current["state"]["carrierId"] is None
    current["time"] = 3
    assert not contextual_features(current, [old], True)["canReason"]
    current["ball"] = None
    assert contextual_features(current, [old], True)["abstentionReason"] == "missing_ball"


def test_runtime_reference_is_loaded_and_versioned():
    result = knowledge()
    assert "cutback" in result["guidance"] and len(result["sha256"]) == 64
