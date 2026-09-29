# Deployment

The full pipeline needs a Python inference process. Static hosting alone only supports the explicitly labeled browser baseline and simulation. The existing optional Pages workflow should not be presented as hosting neural uploads.

## Single-host setup

Install the backend and weights using `bash scripts/setup_backend.sh`, build with `npm ci && npm run build`, and run:

```sh
.venv/bin/python -m uvicorn server.pitchstate.api:app --host 127.0.0.1 --port 8000 --workers 1
```

FastAPI serves `dist` and the API together. Put an HTTPS reverse proxy in front of this listener. Set `PITCHSTATE_PUBLIC=1` and `PITCHSTATE_ORIGIN` to the exact HTTPS origin so cookies are secure and origin checks pass. Keep one worker: the model and queue are process-local. Set proxy upload limits to 100 MB plus multipart overhead, request timeouts appropriately, and bound request rates. The API also checks declared size and received file bytes.

Weights live in `models`; uploads, neural cache, usage ledger and results live in `.local`. Persist this directory across restarts and deployments so Jev caps cannot silently reset. Jobs older than 24 hours are removed on startup or the next upload; configure storage monitoring/maintenance for long-idle deployments and the neural cache. Do not delete the Jev ledger when pruning cached observations.

The default daily cap is 12 jobs globally, with one running worker and at most two active/queued uploads. It is suitable for a small portfolio trial, not a distributed public service. A single visitor can consume the daily quota. An authenticated reverse proxy can restrict access and inject `PITCHSTATE_ACCESS_TOKEN` into **all** `/api/jobs` requests, including video requests. The frontend deliberately has no shared-token input or embedded secret.

## Container option

The supplied Dockerfile packages a CPU backend and built frontend. It excludes local secrets, weights, uploads and research clips from the build context. Download models on the host before starting. A CPU-only container will be slower than local MPS and cannot use Apple's GPU.

```sh
docker build -t pitchstate .
docker run --rm -p 127.0.0.1:8000:8000 \
  --env-file .env.local \
  -v "$PWD/models:/app/models:ro" \
  -v "$PWD/.local:/app/.local" \
  pitchstate
```

Ensure the mounted `.local` directory is writable by container UID 10001. The Docker recipe is provided but has not been built in the implementation environment; local same-origin serving and the inference pipeline have been tested.

## Instant examples and running costs

Use a precomputed analysis and a clip you have permission to publish for an immediate interactive example. Configure `PITCHSTATE_DEMO_VIDEO` and `PITCHSTATE_DEMO_ANALYSIS`; mount both into the service. Generating an example is a one-time inference cost; replay makes no Jev calls. The two downloaded evaluation clips are research inputs and are not bundled for public distribution.

Neural perception runs locally, so it incurs no per-frame API bill. Public uploads still consume your host's CPU/GPU, RAM, disk and bandwidth. Start with cached examples and a deliberately small upload quota. Jev defaults cap lifetime calls and accounted input tokens; these are separate from the daily upload cap. Do not advertise unlimited uploads on free infrastructure.

The Ultralytics runtime and model distribution carry license obligations; review the applicable AGPL/commercial terms and provide corresponding source where required. Dataset/footage permissions are separate from model/runtime licensing.
