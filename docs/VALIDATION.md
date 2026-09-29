# Validation

## Automated checks

17 frontend/core tests cover temporal interpolation, missing evidence, persistence/cooldowns, calibration, annotations, legacy detection/tracking, shot boundaries and causal Jev replay lookup. 13 Python tests cover homography rejection, camera-compensated association, ball expiry/reacquisition, possession hysteresis, invalid geometry, Jev response validation/cache/budget, origin checks, upload ownership/cancellation and daily quotas. HTTP mocks make no paid requests. CI runs both suites, the frontend build, Prettier and Ruff.

These tests validate implementation contracts. They do not establish match-analysis accuracy.

## Real footage, real models, real Jev

Two research clips from Roboflow's soccer example were downloaded locally. The source identifiers are in `models/manifest.json`; videos and weights are excluded from Git. Each frame below was produced by actual neural inference, not manual annotations or generated trajectories.

| Run                      | Samples | Player observations | Track IDs | Ball observed | Ball predicted | Calibration accepted | Possession known |  Runtime | Jev responses |
| ------------------------ | ------: | ------------------: | --------: | ------------: | -------------: | -------------------: | ---------------: | -------: | ------------: |
| First clip, 12 s, v1 CPU |      60 |                1378 |        29 |         65.0% |          23.3% |                 100% |            46.7% |  88.66 s |             9 |
| First clip, 12 s, v2 CPU |      60 |                1378 |        29 |         86.7% |          13.3% |                 100% |            40.0% | 108.10 s |             8 |
| Second clip, 8 s, v2 MPS |      40 |                 927 |        26 |         92.5% |           7.5% |                 100% |            77.5% |  28.42 s |             6 |

The v2 change added overlapping high-resolution ball tiles and stronger reacquisition handling. It recovered several fast/airborne ball observations missed in v1. Lower known possession on the first clip is not necessarily a regression: observed ball motion through a pass can invalidate a previously held carrier hypothesis. This has not been scored against labeled possession.

Coverage measures whether the pipeline produced an observation or accepted transform, **not whether it was correct**. Multiple IDs may belong to one real player after fragmentation. The second clip is an additional development check, not a formally held-out benchmark. Runtime includes inference/state/Jev and varies with hardware/cache; compare CPU versions only as developer measurements.

The local Jev ledger after integration checks recorded 22 distinct successful calls and 72,598 input tokens: estimated $0.0030491 at the documented input-token rate. Per-run response counts can include cached requests and do not sum to distinct billed calls. This is not an account balance.

## End-to-end checks performed

- Loaded the actual 12-second analysis beside original footage and inspected tracked boxes, ball provenance, pitch reconstruction and changing Jev distributions.
- Examined an annotated six-frame contact sheet from real footage, including ball-reacquisition gaps.
- Submitted a real three-second clip through the browser upload flow; received actual detections, state and Jev responses.
- After API restart, submitted the clip through HTTP and verified progressive frame previews before completion, a 15-frame result, real Jev outputs and HTTP 206 video seeking.
- Cancelled another live job and confirmed its terminal state was cancelled.
- Verified separate sessions cannot access or cancel another session's job, and daily quotas reject additional work.
- Frontend build and both test suites pass; no browser console errors were observed in the real upload check.

## Reproduce

Follow the README to acquire models and research footage. Run each clip with `scripts/analyze_clip.py`, specifying `--seconds` and an output path. `scripts/render_evaluation.py` renders inspection frames/contact sheet from the first example. `scripts/diagnose_ball.py` exposes tiled ball candidates on selected difficult frames. Raw neural observations are cached under `.local/perception`; move the matching cache aside for a fresh inference timing, while retaining `.local/jev.sqlite3` so spending controls persist.

## What remains unproven

No labeled ground-truth benchmark yet measures player/ball precision-recall, HOTA/IDF1, pitch reprojection error in meters, possession accuracy, event precision-recall or forecast Brier/log loss. No claim of broadcast-wide robustness or calibrated action probabilities is supported. Long occlusions, camera cuts, close-ups, goalkeeper kit assignment, unseen formations, airborne-ball geometry and rare actions need dedicated evaluation. The container recipe and multi-browser decoder compatibility still require testing in their deployment environments.
