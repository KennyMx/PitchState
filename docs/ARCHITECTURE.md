# Architecture

## Data flow

`pipeline.analyze` samples real decoded video at 5 Hz. `SoccerModels` returns image-space detections and pitch landmarks. `CameraEstimator` estimates camera motion, identifies cuts, and solves image-to-pitch geometry. Player association and ball filtering run before the causal state estimator. That state, plus a short past-only window, becomes the Jev input. After perception completes, a full-clip refinement pass links unambiguous tracklets, applies team consensus and reconstructs short occlusions. State and Jev evaluation then run on the finalized sequence. Every frame and judgment is serialized into a versioned replay consumed by React.

The neural cache stores observations before state inference, allowing tracking/state/prompt iteration without rerunning expensive models. Its version must change when perception preprocessing, weights, or output semantics change. Jev caching hashes model, prompt version, questions and canonical state; no future action labels enter a request, but reconstructed observations incorporate future context. This is a retrospective analysis mode, not a leakage-free forecasting evaluation.

## Perception and geometry

Three soccer-trained Ultralytics models separately detect players/roles, small balls, and 32 field landmarks. Player detections use 960-pixel inference. Ball detection uses global and temporally focused views, with four overlapping high-resolution tiles when confidence is low. Jersey clustering excludes grass from torso crops; track-level voting stabilizes team assignment. Unknown teams remain explicit. Referees are not treated as team players.

Pitch landmarks are mapped onto a nominal 105 × 68 m field. RANSAC, inlier counts, residual and spatial-coverage checks reject bad transforms. Optical flow compensates camera motion and only briefly propagates calibration. A cut clears temporal assumptions. Missing geometry yields image coordinates and suppresses metric tactical conclusions.

A planar homography cannot recover the true ground location of an airborne ball. Partial pitch visibility can also produce a plausible but incorrect calibration. The current quality flag is an internal validity check, not a measured ground-truth error bound.

## Tracking and state

The player tracker uses Hungarian matching with camera-compensated motion, overlap, role and appearance costs, followed by a low-confidence association stage. Tracks expire; IDs are never reused after a shot reset. This is a lightweight association implementation, not a trained long-term re-identification system.

The ball uses a Kalman filter, bounded 0.4-second prediction and gated global reacquisition. Observed, predicted and missing are distinct. State updates consume a past-only window of retrospectively refined frames. Possession requires proximity, temporal hysteresis and expiry; it can remain unknown through a long pass. Metric smoothing rejects implausible player speeds.

Tactical evidence includes visible team width/depth/centroid, closing opponents, open passing lanes, local numerical superiority, forward progression, turnover age and runs behind the second visible defender. Persistent rules produce an inspectable baseline phase and event log. These are hypotheses about visible geometry, not assertions about all 22 players or coaching intent. Attack direction is explicitly configured.

## Jev and replay

Jev periodically evaluates the current evidence and recent trajectory window. It returns a next-three-second action distribution, tactical-phase distribution and dangerous-run judgment. The maintained tactical reference is injected with geometry for crossing territory, box arrivals, clear passing lanes and bounded attacking-team continuity. The UI retains the deterministic evidence alongside the model judgment, exposes uncertainty, and marks old judgments stale. Scrubbing selects the most recent judgment at or before the playhead. Interpolation, trails and heatmaps do not cross shot/coordinate-system boundaries.

## Runtime boundaries

FastAPI accepts bounded multipart jobs into a one-worker queue. Session cookies own jobs and protect results/video. Upload IDs are known before the POST completes so cancellation can target a pending request. Cancellation is cooperative between inference steps; an already-sent Jev request may finish. Only stage/progress information is exposed until the full replay is complete. Persisted unfinished jobs become failed on service restart.

A single process is deliberate: in-memory queue ownership and the model instance are not distributed. SQLite persists the Jev budget/cache. Local job folders hold uploads and replay JSON. Old jobs are removed on startup or a subsequent upload; this is not a continuously running TTL sweeper. Neural caches currently require operator-managed retention.

## Remaining engineering work

Build a labeled evaluation set spanning cuts, zooms, occlusions and kit ambiguity; measure association and calibration errors. Improve ball identity/airborne-state handling, add track correction and direction confirmation, and evaluate tactical/forecast outcomes with proper scoring rules. A multi-user service would need a durable external job queue, streamed upload limits, per-user quotas and managed cache retention before scaling beyond one worker.

## Playback clock

The HTML video decodes the original source cadence. `requestVideoFrameCallback` drives the replay playhead on each presented video frame; animation-frame polling is a compatibility fallback. Pitch coordinates, image boxes and ball image coordinates interpolate between analysis samples. Source FPS and analysis Hz remain distinct. 60 FPS support depends on browser/display/decode capacity; upsampling a test fixture does not create new observed information.

## Level 2 lifecycle and decisions

`decisions.BallControl` distinguishes controlled possession, release, transit, reception, contested/loose ball, uncertain control and unknown evidence. It resets on cuts and does not label possession at clip start as a reception. Each phase/actor boundary increments an epoch. Current possession is unknown during flight even when the last team's context remains useful.

A short trajectory regression estimates possible receiving paths; instantaneous speed and proximity confirm control separately, avoiding delayed reception caused by a smoothed velocity window. Candidates are restricted to visible eligible tracks and include measured passing-lane obstruction. Crossing/shooting candidates require field context. Transit candidates cannot contain a fresh pass by the previous carrier. The model sees current state and short phase/actor history, not future reception outcomes.

Every 5 Hz sample has a separately cached, bounded Jev request. Results include an epoch and exclusive expiry timestamp. Both overlay and sidebar use the same validity function; stale targets and route arrows disappear immediately. Dense judgments are displayed through a decimated set of seek buttons while the full 200 ms sequence remains available in playback and JSON.
