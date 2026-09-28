# PitchState architecture

## Product contract
A visitor sees a replayable tactical playground immediately. The included sequence is explicitly a simulation, not analysis of match footage. Uploaded videos stay on-device. The first detector is an experimental color-based baseline for wide, stable views with red and blue kits; no claim of general broadcast accuracy is made.

## Layers
1. **Observation:** sample a local video at 5 Hz into 480px frames. A worker extracts connected components matching red/blue kit colors. A gated nearest-neighbor tracker assigns stable IDs within each team, with short occlusion tolerance. No inferred ball from this baseline: possession remains unknown.
2. **State:** timestamped player observations and optional ball position form a replayable frame log. Binary search plus interpolation provides synchronized render state at any playhead position. Team geometry and proximity are derived from the current state; no future observations enter event decisions.
3. **Judgment:** deterministic hypotheses use geometric evidence, persistence, and cooldowns. They are heuristics, not calibrated tactical truth. Future Jev judgments should consume a compact state window with explicit unknowns, never raw video. Keys belong on a server, behind quotas and caching. The application works without this service.
4. **Experience:** original clip, top-down projection, movement trails, occupancy visualization, player selection, event timeline, and JSON export share one playhead.

## Geometry and honesty
Simulation positions live on a normalized 105×68m pitch. Uploaded detections use normalized image coordinates, so the view is labeled camera-space and physical speed/distance is withheld. A production path requires field landmark detection and a per-shot homography before reporting meters. Cut detection should invalidate identity and geometry. The first version does not solve either problem.

## Next engineering milestones
- Evaluate a licensed player/ball detector on held-out wide-angle clips; report recall, ID switches and ball visibility rather than a single marketing accuracy.
- Add user-correctable pitch landmarks, RANSAC homography, camera motion compensation, and confidence propagation.
- Replace nearest-neighbor association with motion prediction and appearance matching; explicitly expire identities after cuts.
- Add possession hysteresis and pass hypotheses only when ball evidence is present.
- Compare rules against Jev on annotated tactical windows; assess calibration, abstention, latency, and actual cost before enabling it.

## Cost and deployment
The current site is static: no database, upload storage, GPU server, or paid inference. Vite's dist folder can be served by GitHub Pages, Cloudflare Pages, or any static host. Browser work is capped at 60 seconds and 100MB per clip. Future heavier inference should use cached curated analyses and opt-in local processing before adding a metered backend. Do not ship an unrestricted paid endpoint.
