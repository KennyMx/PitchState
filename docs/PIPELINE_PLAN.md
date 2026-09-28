# Real-footage pipeline implementation

Acceptance: run actual match footage through learned player/ball perception, identity tracking, camera-aware coordinates, evolving game state, tactical features, and real Jev next-action probability distributions. The UI must replay those actual observations and judgments alongside the source video.

Implementation sequence (each independently reviewable step is committed):
1. Reproducible model/footage acquisition and isolated Python inference service.
2. Learned player and ball detectors, with measurable observation quality.
3. Motion/appearance tracking and automatic team separation.
4. Camera motion, cut invalidation, pitch calibration and uncertainty.
5. Stateful possession, movement, team geometry and tactical features.
6. Official Jev adapter, validated response probabilities, durable request budget and cache.
7. Asynchronous upload/job API and replay schema.
8. Frontend integration: original footage overlays, radar and changing probability distributions.
9. Real-footage evaluation, regression tests and deployment paths.

The earlier browser kit-color detector is a legacy lightweight mode, not the full pipeline. Perception failures must be exposed and measured rather than hidden with synthetic positions. No paid GPU service is required for development; inference runs on the local machine. The public deployment must separate cheap cached replay from compute-limited upload jobs.
