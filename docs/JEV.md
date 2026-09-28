# Optional Jev judgment layer

The current application uses deterministic rules and makes no Jev requests. This keeps the public playground usable without account setup or ongoing API costs.

TypeSafe describes Jev as a structured decision model with typed answers and confidence signals: https://typesafe.ai/ and https://docs.typesafe.ai/. Verify the current official SDK, API schema, and pricing before implementing a service. Third-party gateways are not treated as authoritative providers.

## Proposed boundary

A future server adapter receives a compact, versioned window of **already reconstructed state**, not video. The app owns perception, identities, coordinates, and playback. Jev can help judge higher-level hypotheses such as transition, pressure, overload, or insufficient evidence.

Example application-owned input (not a claim about a vendor wire schema):

```json
{
  "schemaVersion": 1,
  "windowSeconds": 3,
  "coordinateSpace": "pitch_meters",
  "calibrationConfidence": 0.7,
  "ballVisibility": 0.9,
  "possession": "home",
  "forwardBallDisplacementMeters": 16,
  "opponentsNearCarrier": 2,
  "teamWidthMeters": 43,
  "previousHypothesis": "build_up",
  "unknowns": ["off_camera_players", "player_roles"]
}
```

Use bounded answers, including `insufficient_evidence`. Keep the rule baseline available when a request fails, times out, or confidence is low. Store provenance separately so the UI cannot mislabel a rule result as a model judgment.

## Cost controls before public enablement

- Quantize state windows and cache judgments by feature hash and judge version.
- Evaluate only meaningful state changes, at a capped rate, not every frame.
- Enforce server-side per-session limits and an overall budget. Do not rely on UI limits.
- Require authentication or another abuse control for paid inference.
- Keep curated demo judgments precomputed and the default upload path local.
- Benchmark on annotated clips against the deterministic baseline. Compare precision, missed events, calibration, latency, and actual observed spend.

An API adapter without validated perception would add expense without fixing the biggest source of error. The next investment should be a reliable, licensed player/ball detector and automatic camera calibration.
