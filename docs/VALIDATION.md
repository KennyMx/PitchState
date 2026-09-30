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

## Offline replay revision

The revised pipeline finishes perception, full-clip refinement, state and Jev computation before returning a replay. Regression tests cover bounded player/ball reconstruction, cut boundaries, conservative tracklet joining, continuous-event deduplication, mirrored crossing geometry, recent-team context expiry and image-space interpolation at 60 Hz from 5 Hz samples.

The first 12-second real clip previously abstained in 6/8 next-action judgments; the revised run abstained in 0/6. This is not an accuracy comparison: schedules differ, inputs changed and outcomes remain unlabeled. See `reports/offline-evaluation.json` for actual distributions/coverage. Retrospective refinement filled 17 player samples and eight ball samples on this clip; none are relabeled as direct detections. No tracklet links passed the conservative gate on this particular clip.

The second real clip was processed for its full 30 seconds (150 samples). It produced eight valid Jev judgments, all with a non-abstention leading action, and one unavailable response after schema/value validation failed. The first eight seconds reused perception cache, so its 70.36-second runtime is not a cold benchmark. Do not interpret plentiful pass predictions on these build-up sequences as proof of rare-action recognition.

An opt-in four-call synthetic sensitivity check (`scripts/evaluate_action_context.py`) produced cross probabilities of 19% on a wide approach, 93% at the byline with box targets, and 23% with an empty box. A missing-ball/unknown-team case abstained at 100%. These test model sensitivity to our context, not forecast accuracy or calibrated percentages. Exact results and the tactical reference hash are committed in `reports/action-context-sensitivity.json`.

A real three-second segment re-encoded at 60 FPS was uploaded through the browser. Processing completed before replay opened, the result retained 60 FPS source metadata and 5 Hz analysis, and Play drove the native video-frame clock with interpolated overlays. This tests cadence compatibility; duplicated source frames add no information, and no hardware-independent sustained-rendering performance guarantee is implied.

## Level 2: concrete decisions at 5 Hz

The 12-second real clip now has 60 decision slots: 58 valid cached/live responses and two earlier failed requests that are deliberately not paid-retried. The second eight-second clip has 40 slots with 39 valid responses. A browser upload of a real three-second segment encoded at 60 FPS completed with all 15 Level 2 decisions. These runs reuse neural caches; runtimes are not cold inference benchmarks.

The video visibly changes from “NOW #4 on the ball / NEXT #4 → #2 pass” to “NOW Ball in transit / NEXT #23 receives.” These are actual model outputs on inferred state, not annotations establishing the correct recipient. Model confidence can be overconfident; no ground-truth recipient benchmark has been completed.

`scripts/evaluate_level2.py` audits epoch validity, 200 ms expiry, probability normalization, visible target references, and the absence of new pass/carry/cross/shot options during transit. All three replay audits pass; see `reports/level2-evaluation.json`. It makes no network calls. Regression tests additionally exercise control→release→reception, clip-start versus reception, camera-cut resets, visible teammate candidates, dynamic Jev criteria, category aggregation, rounding provenance and UI invalidation.

Two-decimal model distributions occasionally sum to 0.99 or 1.01. Validation accepts only a bounded rounding discrepancy, records raw probabilities and their sum, and normalizes the displayed distribution. Two actual upload responses exercised this path. Larger errors, failed requests and missing evidence remain explicit rather than borrowing an old forecast. Earlier failures are preserved in the durable ledger.

The suite now has 25 Python and 19 frontend/core tests. Production build, formatting and lint pass. The development ledger accounts for roughly 6.5 cents across all project testing at the documented rate, including conservative reservations; this is not the provider invoice. Local caps remain enabled. Ball height, off-camera targets, true jersey identity and labeled forecast accuracy remain unresolved research areas.
