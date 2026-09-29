from server.pitchstate.refinement import refine


def frame(t, identity=1, shot=0):
    p = {
        "id": identity,
        "x": 30 + t,
        "y": 50,
        "team": "home",
        "teamConfidence": 0.9,
        "confidence": 0.9,
        "role": "player",
        "_appearance": [0.3, 0.2, 0.1],
    }
    return {
        "time": t,
        "players": [p] if identity else [],
        "ball": dict(x=31 + t, y=50, status="observed", confidence=0.8),
        "calibration": {"valid": True, "shot": shot},
        "coordinateSpace": "pitch",
    }


def test_reconstructs_bounded_occlusion_without_claiming_observation():
    frames = [frame(0), frame(0.2, None), frame(0.4)]
    frames[1]["ball"] = None
    out, stats = refine(frames)
    assert out[1]["players"][0]["status"] == "reconstructed"
    assert out[1]["ball"]["status"] == "reconstructed"
    assert stats["reconstructedBallSamples"] == 1
    assert not frames[1]["players"]  # original evidence retained


def test_links_unambiguous_tracklet_but_never_across_cut():
    out, stats = refine([frame(0), frame(0.2, 2)])
    assert stats["linkedTracklets"] == 1
    assert out[1]["players"][0]["id"] == 1
    out, stats = refine([frame(0), frame(0.2, 2, shot=1)])
    assert stats["linkedTracklets"] == 0


def test_long_ball_gap_remains_unknown():
    frames = [frame(0), frame(0.6, None), frame(1.2)]
    frames[1]["ball"] = None
    out, _ = refine(frames)
    assert out[1]["ball"] is None
