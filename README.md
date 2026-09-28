# PitchState

**See the game beneath the game.** A local-first soccer analysis playground built with React, TypeScript, Canvas, SVG, and a Web Worker.

PitchState connects original footage, player movement, pitch reconstruction, and evolving tactical hypotheses to a single playhead. An interactive simulated play loads immediately; visitors can also process their own clips without sending video to a server.

## Run locally

Use Node 22 LTS or Node 24+.

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:5173. `npm test` runs the analysis tests, `npm run build` creates the static site in `dist`, and `npm run format:check` checks formatting.

## Explore

- Play or scrub the example. Both views, game state, and movement history follow the same clock.
- Select a player, turn on the heatmap, and inspect speed and distance in **Player focus**.
- Click a tactical moment to inspect its geometric evidence.
- Upload an MP4 or WebM, up to 60 seconds and 100 MB. Red kits become Home; blue kits become Away. All processing stays on-device.
- With a **fixed camera and the whole pitch visible**, choose **Calibrate pitch**. Mark the pitch corners clockwise: top left, top right, bottom right, bottom left. This assumes Home attacks toward the right.
- Choose **Mark ball** and click the ball in the original footage. Each click advances 0.4 seconds. Mark a sequence, then choose **Finish ball marking** and replay it. Marks interpolate only over gaps up to two seconds; other spans remain unknown.
- Export the frame log, events, calibration, and annotations as JSON. There is no persistence across page reloads yet.

The included `tests/fixtures/kits.mp4` is a generated three-second detector smoke-test clip, not soccer footage. It has one red and one blue rectangle on green.

## What is real, and what is experimental?

| Capability           | Current implementation                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| Instant example      | Explicitly labeled simulated positions and ball movement                                                 |
| Uploaded video       | Real local decoding and sampling at 5 Hz                                                                 |
| Player candidates    | Kit-color connected components, worker processing, gated temporal identity association                   |
| Pitch reconstruction | Camera-space view by default; manual four-corner projective calibration                                  |
| Ball position        | User annotations with bounded interpolation; no automatic ball detector                                  |
| Tactical state       | Ball proximity, nearby opponents, progression and final-third rules with persistence and event cooldowns |
| Movement metrics     | Trails and occupancy; approximate meters and km/h only for simulation or calibrated clips                |
| Jev                  | Architectural integration point only; no API calls, key, or paid service required                        |

**This is an assisted analysis prototype, not a general broadcast-soccer analyzer.** The baseline can confuse spectators, advertising, referees, and similarly colored objects with players. Occlusions can change IDs. Zooms, camera movement, cuts, or incorrect corners invalidate calibration. Speed estimates inherit those errors. Tactical confidence values are heuristic weights, not calibrated probabilities. Pressing intent, counterattacks, overloads, pass recognition, and automatic ball tracking remain research milestones.

The visualization deliberately distinguishes simulated data, low-confidence observations, uncalibrated coordinates, and unknown possession. It does not fabricate tactical conclusions where the ball is missing.

## Engineering depth

- A replayable, timestamped observation model decouples perception, state, judgment, and rendering.
- Binary-search lookup and interpolation support arbitrary seeking without coupling state to playback order.
- Connected-component labeling runs off the UI thread; local processing supports progress, cancellation, decoder errors, and bounded resource use.
- Temporal association includes team gating, distance gating, one-to-one assignment, and track expiry.
- Four-point homography uses partial-pivot elimination with degenerate-input validation.
- Tactical rules require persistence and enforce cooldowns. Ball interpolation explicitly abstains across long gaps.
- Tests cover temporal state, unknown evidence, event stability, tracking identities, detection, calibration, and annotation gaps.

See [architecture and roadmap](docs/ARCHITECTURE.md), [Jev integration design](docs/JEV.md), and [validation notes](docs/VALIDATION.md).

## Deploy without an inference bill

The app builds to static files. There is no backend, database, video storage, GPU service, or inference API. Hosting bandwidth is the only server-side resource. Fonts are fetched from Google Fonts with system fallbacks; video is never transmitted.

For GitHub Pages, set **Settings → Pages → Source → GitHub Actions**, then run **Publish to GitHub Pages** in the Actions tab. The workflow is manual so a push does not publish the project unexpectedly. Vite uses relative asset paths for repository subpath hosting. This repository does not claim a live deployment until that workflow succeeds.

Other static hosts can use `npm run build` and the `dist` output directory. Never place a Jev key in a `VITE_*` environment variable or the browser bundle.
