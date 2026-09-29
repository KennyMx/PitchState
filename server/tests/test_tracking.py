import numpy as np
from server.pitchstate.tracking import PlayerTracker, BallTracker
from server.pitchstate.perception import Detection


def test_tracks_survive_camera_pan_and_ids_reset_at_cuts():
    image = np.zeros((200, 400, 3), np.uint8)
    tracker = PlayerTracker()
    a = tracker.update(image, [Detection([50, 50, 70, 100], 0.9, "player")], 0)[0].id
    motion = np.array([[1, 0, 100], [0, 1, 0], [0, 0, 1]], float)
    b = tracker.update(image, [Detection([150, 50, 170, 100], 0.9, "player")], 0.2, motion)[0].id
    assert a == b
    tracker.reset()
    assert tracker.update(image, [Detection([150, 50, 170, 100], 0.9, "player")], 0.4)[0].id != a


def test_ball_abstains_after_missing_interval():
    tracker = BallTracker()
    ball = Detection([10, 10, 15, 15], 0.9, "ball")
    assert tracker.update([ball], 0, 100)["status"] == "observed"
    assert tracker.update([], 0.2, 100)["status"] == "predicted"
    assert tracker.update([], 1, 100) is None


def test_strong_global_ball_reacquisition_resets_stale_motion():
    tracker = BallTracker()
    tracker.update([Detection([10, 10, 15, 15], 0.9, "ball")], 0, 400)
    result = tracker.update([Detection([85, 10, 95, 20], 0.9, "ball")], 0.2, 400)
    assert result["status"] == "observed"
    assert abs(result["point"][0] - 90) < 1
