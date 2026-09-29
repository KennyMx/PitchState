# Jev integration

The implementation calls the [official TypeSafe API](https://docs.typesafe.ai/api) at `https://api.typesafe.ai/v1/systemone`, using `jev-1.13.0`. `server/pitchstate/jev.py` is the adapter; it has been exercised with actual soccer state and actual responses.

## Inputs and outputs

Each request contains a compact reconstructed state/history and three typed questions:

- Choice: the next on-ball action in three seconds — pass, carry, shot, cross, turnover, stoppage or insufficient evidence.
- Choice: build-up, counterattack, pressing, settled attack, defensive transition or insufficient evidence.
- Noul: whether observed motion supports a dangerous off-ball run.

A cross is explicitly separate from a pass. Inputs include geometry validity, ball provenance, possession confidence, pressure, passing options, progression, team shape and transition history. Raw video, image crops, filenames and the API key are not part of state. Questions instruct the model to avoid inventing off-camera players and to abstain when evidence is insufficient.

Responses are validated for supported choices, finite [0,1] values and normalized distributions. A failed or invalid response becomes unavailable, never a synthetic probability. Results include source, model, prompt version, timestamp, request hash, cache status, latency and usage. These are model judgments, not statistically calibrated match-outcome probabilities.

## Cost controls

`JEV_API_KEY` is server-only and loaded from ignored `.env.local` or the runtime environment. No secret belongs in a `VITE_*` variable. Requests go only to the pinned official endpoint with redirects disabled.

Defaults are 60 lifetime requests, 250,000 accounted input tokens and 12 calls per job. SQLite reserves conservative tokens before transmission, then records actual returned usage. Failed/ambiguous requests keep their reservation and are not automatically retried. The limits survive a process restart **only if `.local/jev.sqlite3` persists**. Do not delete this file to clear an analysis cache.

The maintained `docs/TACTICAL_REFERENCE.md` runtime section is included in requests with its content hash. Context features distinguish confirmed carrier control from nearby-player hypotheses and bounded recent-team ball-flight context. Unknown carrier alone no longer triggers automatic abstention.

The state payload is bounded to 24 KB. Judgments are distributed across the clip with a minimum one-second spacing and the per-job budget. Low caps on long clips can leave stale intervals, which remain labeled in replay. Identical canonical requests use a content-addressed cache. When the budget is exhausted, the neural/state pipeline continues and the UI reports unavailable Jev judgments.

The estimate uses the published $0.042 per million input tokens for Jev 1.13.0, with free output tokens, checked during implementation against [model documentation](https://docs.typesafe.ai/models). It is an estimate, not an account balance or provider invoice. Public workloads are additionally bounded by the daily job limit. Change caps deliberately rather than treating available credit as an instruction to consume it.
