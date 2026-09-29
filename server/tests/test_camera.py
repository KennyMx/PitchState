import numpy as np
from server.pitchstate.camera import fit_pitch, PITCH_POINTS, transform


def test_recovers_known_projective_camera():
    inverse = np.array([[10, 3, 100], [0, 5, 200], [0, 0.004, 1]], dtype=float)
    pixels = transform(PITCH_POINTS, inverse)
    points = np.column_stack([pixels, np.ones(32)])
    recovered, quality = fit_pitch(points, 1920, 1080)
    assert quality["valid"]
    assert np.max(np.abs(transform(pixels, recovered) - PITCH_POINTS)) < 0.01


def test_missing_or_collinear_landmarks_abstain():
    assert fit_pitch(np.zeros((32, 3)), 1920, 1080)[0] is None
    assert fit_pitch(np.zeros((0, 3)), 1920, 1080)[0] is None
