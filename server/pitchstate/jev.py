"""Bounded, cached access to the official Jev API. No video or credentials enter replay JSON."""

from __future__ import annotations
import hashlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
import httpx

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
PROMPT_VERSION = "soccer-level2-v3"
ACTIONS = {
    "receive": "Control or reception of a ball already released; not a new pass.",
    "pass": "A pass to a teammate, excluding a cross into the penalty area.",
    "carry": "The carrier keeps the ball and advances by dribbling.",
    "shot": "An attempt to score at goal.",
    "cross": "A delivery from a wide area into the penalty area.",
    "turnover": "The opponent wins the ball before another on-ball action.",
    "stoppage": "The ball leaves play or play stops.",
    "insufficient_evidence": "Ball, possession, camera geometry, or temporal evidence is too unreliable.",
}
PHASES = {
    "build_up": "Controlled progression from a deeper area against an organized defense.",
    "counterattack": "Rapid forward transition shortly after winning possession against a recovering defense.",
    "pressing": "Multiple defenders actively close the ball carrier or nearby passing options.",
    "settled_attack": "Sustained attacking possession against an established defense.",
    "defensive_transition": "A side just lost possession and is recovering its defensive shape.",
    "insufficient_evidence": "No defensible phase can be inferred even from recent team and location context.",
}
QUESTIONS = {
    "next_action": {
        "type": "choice",
        "instructions": "Use tacticalReference guidance, current.context and recent history. Predict the NEXT initiated action, not the pass already in flight. With useful attacking-team and location context, uncertainty should broaden realistic action probabilities rather than force abstention. Based on the reconstructed soccer state, which next observable on-ball action is most likely in the next 3 seconds? This is a forecast, not advice. The options are mutually exclusive; a cross is not counted as a pass. Do not invent off-camera players or treat unknown coordinates as facts. Choose insufficient_evidence only when no defensible contextual judgment is possible. Unknown carrier alone is not sufficient to abstain.",
        "criteria": ACTIONS,
    },
    "phase": {
        "type": "choice",
        "instructions": "Which tactical phase best describes the current soccer play, using possession transitions, geometry, ball movement and pressure evidence? Geometric proximity alone is not proof of pressing or a counterattack. Prefer insufficient_evidence when unsupported.",
        "criteria": PHASES,
    },
    "dangerous_run": {
        "type": "noul",
        "instructions": "Does the supplied observed history support an attacking off-ball run behind the defensive line? Require forward player motion and valid pitch calibration. If these observations are missing, answer no.",
    },
}


class JevUnavailable(Exception):
    pass


def validate_choice(answer: dict, options: dict) -> dict:
    probabilities = answer.get("probabilities", {})
    if answer.get("type") != "choice" or set(probabilities) != set(options):
        raise ValueError("Jev returned an incompatible choice schema")
    numbers = list(probabilities.values())
    if any(
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or not math.isfinite(v)
        or not 0 <= v <= 1
        for v in numbers
    ):
        raise ValueError("Jev returned invalid probabilities")
    if abs(sum(numbers) - 1) > 0.002 or answer.get("choice") not in options:
        raise ValueError("Jev returned an invalid distribution")
    confidence = answer.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Jev returned invalid confidence")
    return {"choice": answer["choice"], "probabilities": probabilities, "confidence": confidence}


class JevJudge:
    def __init__(
        self,
        directory: Path,
        api_key: str | None = None,
        max_calls: int | None = None,
        max_tokens: int | None = None,
        client=None,
    ):
        self.key = api_key if api_key is not None else os.getenv("JEV_API_KEY", "")
        self.max_calls = (
            max_calls if max_calls is not None else int(os.getenv("JEV_MAX_CALLS", "300"))
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else int(os.getenv("JEV_MAX_INPUT_TOKENS", "1500000"))
        )
        directory.mkdir(parents=True, exist_ok=True)
        self.db = directory / "jev.sqlite3"
        self.client = client
        with self.connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS calls (hash TEXT PRIMARY KEY, tokens INTEGER NOT NULL, status TEXT NOT NULL, response TEXT, created REAL NOT NULL)"
            )

    def connection(self):
        return sqlite3.connect(self.db, timeout=30)

    def usage(self):
        with self.connection() as conn:
            row = conn.execute("SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM calls").fetchone()
            actual = conn.execute("SELECT COUNT(*) FROM calls WHERE status='complete'").fetchone()[
                0
            ]
        return {
            "reservedCalls": row[0],
            "completedCalls": actual,
            "accountedInputTokens": row[1],
            "maxCalls": self.max_calls,
            "maxInputTokens": self.max_tokens,
            "estimatedCostUsd": round(row[1] * 0.042 / 1_000_000, 7),
        }

    def judge(self, state: dict[str, Any]) -> dict:
        if not self.key:
            raise JevUnavailable("Jev is not configured on the server")
        candidates = state.get("decisionCandidates") or []
        questions = QUESTIONS
        if candidates:
            criteria = {
                c["id"]: c["label"] + ". Evidence: " + json.dumps(c.get("evidence", {}))
                for c in candidates
            }
            questions = {
                **QUESTIONS,
                "next_action": {
                    "type": "choice",
                    "instructions": "Select the most likely NEXT event within three seconds from these concrete options. Use current.ballControl and tacticalReference. IDs are tracks, not jersey numbers. During released/in_transit, the pass has ALREADY happened: forecast reception/interception, never another pass by the previous carrier. During control, compare specific visible recipients, lane blockage, distance, pressure and crossing context. Do not invent a recipient. Use other target or insufficient evidence when appropriate. Criteria are mutually exclusive alternatives; unresolved reception means a receiver OTHER than the named candidates or unidentifiable. Unknown ball and control should favor insufficient_evidence. Probabilities must sum to one.",
                    "criteria": criteria,
                },
            }
        payload = {"model": MODEL, "state": state, "questions": questions}
        encoded = json.dumps(
            payload, sort_keys=True, allow_nan=False, separators=(",", ":")
        ).encode()
        if len(encoded) > 32000:
            raise JevUnavailable("State exceeds the bounded Jev request size")
        digest = hashlib.sha256(PROMPT_VERSION.encode() + encoded).hexdigest()
        # Reserve conservatively before transmission. Ambiguous/failed requests remain charged
        # against our local budget. No implicit retries can double-spend the user's allowance.
        reserved = len(encoded) + 1024
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT status,response FROM calls WHERE hash=?", (digest,)
            ).fetchone()
            if existing:
                if existing[0] == "complete":
                    return {**json.loads(existing[1]), "cached": True}
                raise JevUnavailable(
                    "This request already failed or is in progress; no paid automatic retry"
                )
            count, tokens = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM calls"
            ).fetchone()
            if count >= self.max_calls or tokens + reserved > self.max_tokens:
                raise JevUnavailable("Configured Jev test budget reached")
            conn.execute(
                "INSERT INTO calls VALUES (?,?,?,?,?)",
                (digest, reserved, "pending", None, time.time()),
            )
        started = time.monotonic()
        try:
            client = self.client or httpx.Client(timeout=25, follow_redirects=False)
            try:
                response = client.post(
                    ENDPOINT, headers={"Authorization": f"Bearer {self.key}"}, json=payload
                )
            finally:
                if self.client is None:
                    client.close()
            if response.status_code != 200:
                raise JevUnavailable(
                    f"Jev returned HTTP {response.status_code}; request not retried"
                )
            body = response.json()
            answers = body["answers"]
            dangerous = answers["dangerous_run"]["noul"]
            if (
                not isinstance(dangerous, (int, float))
                or not math.isfinite(dangerous)
                or not 0 <= dangerous <= 1
            ):
                raise ValueError("Invalid Noul response")
            result = {
                "source": "jev",
                "model": body["model"],
                "promptVersion": PROMPT_VERSION,
                "requestHash": digest,
                "cached": False,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "nextAction": validate_choice(
                    answers["next_action"], questions["next_action"]["criteria"]
                ),
                "phase": validate_choice(answers["phase"], PHASES),
                "dangerousRunProbability": dangerous,
                "usage": body["usage"],
            }
            if candidates:
                decision = result["nextAction"]
                result["nextDecision"] = decision
                result["candidates"] = candidates
                totals = {kind: 0.0 for kind in ACTIONS}
                for candidate in candidates:
                    totals[candidate["kind"]] += decision["probabilities"][candidate["id"]]
                result["nextAction"] = {
                    "choice": max(totals, key=totals.get),
                    "probabilities": totals,
                    "confidence": decision["confidence"],
                }
            actual = int(body["usage"]["input_tokens"])
            if actual < 0:
                raise ValueError("Invalid token usage")
            with self.connection() as conn:
                conn.execute(
                    "UPDATE calls SET status='complete',tokens=?,response=? WHERE hash=?",
                    (actual, json.dumps(result, allow_nan=False), digest),
                )
            return result
        except Exception as exc:
            with self.connection() as conn:
                conn.execute("UPDATE calls SET status='failed' WHERE hash=?", (digest,))
            if isinstance(exc, JevUnavailable):
                raise
            # Never relay response bodies, headers or an exception that may contain credentials.
            raise JevUnavailable(
                f"Jev request failed ({type(exc).__name__}); no automatic retry"
            ) from None
