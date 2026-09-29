# PitchState

**See the game beneath the game.** Upload a soccer clip and replay learned player/ball detections, a moving pitch reconstruction, evolving tactical evidence, and Jev next-action probabilities on one timeline.

The default upload path is a working neural pipeline:

**Footage → soccer-specific perception → camera-aware tracking → causal game state → tactical evidence → Jev → next-three-second action distribution.**

React/TypeScript renders the replay. A Python/FastAPI companion runs three local soccer models and sends compact state features to Jev. Raw video is not sent to Jev. A cached real analysis loads immediately when configured; a clearly labeled simulation is the fallback. The earlier kit-color browser baseline remains available for comparison.

## Run

Use Node 22 and Python 3.10+. The tested environment is macOS with Apple MPS; CUDA and CPU are also selectable. Model downloads total approximately 414 MB; Python/Torch needs additional disk space.

```sh
npm ci
bash scripts/setup_backend.sh
cp .env.example .env.local
# Set JEV_API_KEY in .env.local. Never use a VITE_* variable for secrets.
npm run server
```

In another terminal:

```sh
npm run dev
```

Open http://127.0.0.1:5173. Upload an MP4/WebM/MOV (up to 60 seconds, 100 MB, 4K). Team A is initially the darker jersey cluster; choose its attack direction before processing. The first provisional reconstruction appears while analysis continues. Play, scrub, select tracks, inspect movement, and click Jev timestamps or tactical moments. Export the complete replay JSON for inspection.

Without a Jev key, perception and tactical state still work; the interface reports unavailable judgments instead of fabricating probabilities.

## Reproduce the real-footage evaluation

The downloader references public links from [Roboflow's soccer example](https://github.com/roboflow/sports/tree/main/examples/soccer). These research clips are not bundled or cleared for public redistribution.

```sh
.venv/bin/python scripts/download_assets.py --footage
PYTHONPATH=. .venv/bin/python scripts/analyze_clip.py data/2e57b9_0.mp4 \
  --seconds 12 --jev --output .local/real-analysis.json
```

Reload the application to open the real cached example. A second clip is available as `data/0bfacc_0.mp4`. `--jev` makes actual paid requests within the configured caps; omit it for perception/state evaluation. Repeated identical state requests use the persistent cache.

| Real evaluation             | Samples | Observed ball coverage | Processing time |
| --------------------------- | ------: | ---------------------: | --------------: |
| First clip, 12 seconds, CPU |      60 |                  86.7% |         108.1 s |
| Second clip, 8 seconds, MPS |      40 |                  92.5% |          28.4 s |

Coverage measures availability, **not accuracy**. These are development runs on different clips/devices, not a controlled hardware comparison. Both produced actual Jev distributions. See [validation](docs/VALIDATION.md) and [machine-readable reports](reports/real-footage-baseline.json).

## What is implemented

- Soccer-trained player, goalkeeper, referee, ball and pitch-landmark models; tiled small-ball reacquisition.
- Camera motion compensation, two-stage track association, ball filtering, bounded prediction, and shot resets.
- Learned pitch calibration with RANSAC and rejection checks; explicit camera-space fallback.
- Possession hysteresis, movement estimates, visible team shape, pressure, passing options, local overloads, dangerous-run candidates and transition evidence.
- Causal Jev questions with complete next-action distributions, timestamps, abstention and stale-judgment indicators.
- Progressive jobs, cancellation, private session ownership, persistent caches, durable API budget, daily upload cap and replay export.

This is an operational research project, not a validated professional tracking system. Ball occlusion, airborne-ball projection, crowded scenes, similar kits, unusual camera angles and partial-field views remain hard. IDs are track IDs, not player identities. Speed/distance and tactical labels inherit perception errors. Jev probabilities have not been calibrated against labeled match outcomes.

## Engineering and deployment

Read [architecture](docs/ARCHITECTURE.md), [Jev integration](docs/JEV.md), [validation](docs/VALIDATION.md), and [deployment](docs/DEPLOYMENT.md).

```sh
npm test
npm run build
npm run format:check
pip install -r server/requirements-test.txt  # inside the backend environment
npm run test:server
.venv/bin/ruff check server scripts
```

A static-only deployment can run the browser baseline, but **neural uploads require the Python service**. The included single-worker container setup bounds cost and serves the frontend/API together. No public deployment is claimed. Model/runtime license obligations and footage rights must be resolved for the intended deployment; see `models/manifest.json`.
