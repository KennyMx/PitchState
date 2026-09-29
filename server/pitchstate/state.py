"""Causal game-state estimator. No frame after the current timestamp is consulted."""

from collections import deque
import numpy as np
from .tactics import contextual_features, knowledge


def metric(point):
    return np.array([point["x"] * 1.05, point["y"] * 0.68])


def dist(a, b):
    return float(np.linalg.norm(metric(a) - metric(b)))


class GameState:
    def __init__(self, home_attacks_right=True):
        self.knowledge = knowledge()
        self.direction = 1 if home_attacks_right else -1
        self.history = deque(maxlen=40)
        self.previous = {}
        self.distance = {}
        self.velocities = {}
        self.owner = None
        self.carrier = None
        self.candidate = None
        self.candidate_since = 0.0
        self.last_control = -10.0
        self.last_change = -10.0
        self.prior_owner = None
        self.last_shot = None
        self.events = []
        self.signal_since = {}
        self.emitted_signals = set()
        self.last_event = {}

    def reset_shot(self):
        self.previous.clear()
        self.velocities.clear()
        self.history.clear()
        self.owner = None
        self.carrier = None
        self.candidate = None
        self.last_control = -10.0
        self.prior_owner = None
        self.last_change = -10.0
        self.signal_since.clear()
        self.emitted_signals.clear()

    def update(self, frame):
        t = frame["time"]
        valid = frame["calibration"]["valid"]
        shot = frame["calibration"]["shot"]
        if self.last_shot is not None and shot != self.last_shot:
            self.reset_shot()
        self.last_shot = shot
        players = [
            p
            for p in frame["players"]
            if p["team"] in ("home", "away") and p.get("role") != "referee"
        ]
        current = {}
        for p in frame["players"]:
            old = self.previous.get(p["id"])
            point = metric(p)
            p["speedMps"] = None
            p["distanceMeters"] = round(self.distance.get(p["id"], 0), 2) if valid else None
            if old is not None and valid and old["valid"] and 0 < t - old["time"] <= 0.6:
                delta = point - old["point"]
                dt = t - old["time"]
                raw = delta / dt
                if np.linalg.norm(raw) < 13:
                    velocity = 0.6 * self.velocities.get(p["id"], raw) + 0.4 * raw
                    self.velocities[p["id"]] = velocity
                    self.distance[p["id"]] = self.distance.get(p["id"], 0) + float(
                        np.linalg.norm(delta)
                    )
                    p["speedMps"] = round(float(np.linalg.norm(velocity)), 2)
                    p["distanceMeters"] = round(self.distance[p["id"]], 2)
            current[p["id"]] = {"point": point, "time": t, "valid": valid}
        self.previous = current
        ball = frame.get("ball")
        observed = (
            ball is not None
            and ball.get("status") in ("observed", "reconstructed")
            and ball.get("confidence", 0) >= 0.12
            and valid
        )
        nearest = min(players, key=lambda p: dist(p, ball), default=None) if observed else None
        candidate = nearest if nearest is not None and dist(nearest, ball) <= 3.0 else None
        if candidate:
            key = (candidate["team"], candidate["id"])
            if key != self.candidate:
                self.candidate = key
                self.candidate_since = t
            if t - self.candidate_since >= 0.35:
                if self.owner is not None and self.owner != candidate["team"]:
                    self.prior_owner = self.owner
                    self.last_change = t
                self.owner = candidate["team"]
                self.carrier = candidate["id"]
                self.last_control = t
            elif self.owner == candidate["team"]:
                self.carrier = candidate["id"]
                self.last_control = t
        else:
            self.candidate = None
        if not valid or t - self.last_control > 0.6:
            self.owner = None
            self.carrier = None
        teams = {}
        for team in ("home", "away"):
            group = [p for p in players if p["team"] == team]
            points = np.array([metric(p) for p in group])
            teams[team] = {
                "visiblePlayers": len(group),
                "widthMeters": round(float(np.ptp(points[:, 1])), 2)
                if valid and len(points) > 1
                else None,
                "depthMeters": round(float(np.ptp(points[:, 0])), 2)
                if valid and len(points) > 1
                else None,
                "centroid": np.mean(points, axis=0).round(2).tolist()
                if valid and len(points)
                else None,
            }
        ball_speed = None
        progress = None
        if observed and self.history:
            prior = next(
                (
                    f
                    for f in reversed(self.history)
                    if f["ball"] is not None and f["calibration"]["valid"] and t - f["time"] >= 0.4
                ),
                None,
            )
            if prior and t - prior["time"] <= 1.2:
                velocity = (metric(ball) - metric(prior["ball"])) / (t - prior["time"])
                if np.linalg.norm(velocity) < 45:
                    ball_speed = round(float(np.linalg.norm(velocity)), 2)
                    if self.owner:
                        progress = round(
                            float(
                                velocity[0]
                                * (self.direction if self.owner == "home" else -self.direction)
                            ),
                            2,
                        )
        opponents = [p for p in players if self.owner and p["team"] != self.owner]
        attackers = [p for p in players if p["team"] == self.owner]
        pressure = [p for p in opponents if observed and dist(p, ball) < 6]
        closing = []
        for p in pressure:
            v = self.velocities.get(p["id"])
            toward = metric(ball) - metric(p)
            if v is not None and float(np.dot(v, toward) / max(1, np.linalg.norm(toward))) > 1:
                closing.append(p["id"])
        open_options = []
        if observed and self.owner:
            for p in attackers:
                if p["id"] == self.carrier or not 3 < dist(p, ball) < 25:
                    continue
                if all(dist(p, o) > 3 for o in opponents):
                    open_options.append(p["id"])
        attack_direction = self.direction if self.owner == "home" else -self.direction
        final_third = bool(
            observed
            and self.owner
            and (ball["x"] > 66.7 if attack_direction == 1 else ball["x"] < 33.3)
        )
        local_a = [p for p in attackers if observed and dist(p, ball) < 15]
        local_d = [p for p in opponents if observed and dist(p, ball) < 15]
        overload = len(local_a) >= 3 and len(local_a) >= len(local_d) + 2
        runs = []
        if observed and len(opponents) >= 3:
            defenders = sorted([p["x"] * attack_direction for p in opponents], reverse=True)
            for p in attackers:
                velocity = self.velocities.get(p["id"])
                if (
                    p["id"] != self.carrier
                    and velocity is not None
                    and velocity[0] * attack_direction > 3
                    and p["x"] * attack_direction > defenders[1]
                    and abs(p["y"] - ball["y"]) < 35
                ):
                    runs.append(p["id"])
        phase = "insufficient_evidence"
        if valid and self.owner and observed:
            phase = "settled_attack" if final_third else "build_up"
            if t - self.last_change < 5 and progress is not None and progress > 3:
                phase = "counterattack"
            elif len(pressure) >= 2 and closing:
                phase = "pressing"
            elif t - self.last_change < 2:
                phase = "defensive_transition"
        evidence = {
            "pressureCount": len(pressure),
            "closingOpponents": closing,
            "openPassOptions": open_options,
            "ballSpeedMps": ball_speed,
            "forwardProgressMps": progress,
            "finalThird": final_third,
            "localAttackers": len(local_a),
            "localDefenders": len(local_d),
            "overload": overload,
            "dangerousRunIds": runs,
            "secondsSinceTurnover": round(t - self.last_change, 2)
            if self.last_change >= 0
            else None,
        }
        state = {
            "possession": self.owner or "unknown",
            "carrierId": self.carrier,
            "phase": phase,
            "teams": teams,
            "evidence": evidence,
            "homeAttacksRight": self.direction == 1,
            "possessionConfidence": round(
                min(ball.get("confidence", 0), nearest.get("teamConfidence", 0)), 3
            )
            if self.owner and observed and nearest
            else 0,
        }
        frame["state"] = state
        state["context"] = contextual_features(frame, self.history, self.direction == 1)
        if phase == "insufficient_evidence" and state["context"]["canReason"]:
            # A plausible attacking team and location support a broad phase even during a pass.
            phase = (
                "settled_attack"
                if state["context"]["distanceToGoalLineMeters"] < 35
                else "build_up"
            )
            state["phase"] = phase
            state["phaseSource"] = "context_hypothesis"
        else:
            state["phaseSource"] = "controlled_possession"
        signals = {phase} if phase != "insufficient_evidence" else set()
        if overload:
            signals.add("overload")
        if runs:
            signals.add("dangerous_run")
        if final_third:
            signals.add("final_third_entry")
        for key in list(self.signal_since):
            if key not in signals:
                self.signal_since.pop(key)
                self.emitted_signals.discard(key)
        for key in signals:
            self.signal_since.setdefault(key, t)
            if (
                key not in self.emitted_signals
                and t - self.signal_since[key] >= 0.6
                and t - self.last_event.get(key, -100) > 4
            ):
                self.events.append(
                    {
                        "time": round(self.signal_since[key], 3),
                        "kind": key,
                        "detail": "Attacking-team context and field location support this phase; carrier control remains uncertain."
                        if key == phase and state["phaseSource"] == "context_hypothesis"
                        else self.explain(key, evidence),
                        "confidence": state["possessionConfidence"],
                        "source": "state_rules",
                    }
                )
                self.last_event[key] = t
                self.emitted_signals.add(key)
        self.history.append(frame)
        return state

    @staticmethod
    def explain(kind, evidence):
        if kind == "pressing":
            return f"{evidence['pressureCount']} opponents within 6m; {len(evidence['closingOpponents'])} closing toward the ball."
        if kind == "counterattack":
            return f"Possession changed recently; forward ball progression {evidence['forwardProgressMps']} m/s."
        if kind == "overload":
            return f"Local numerical advantage: {evidence['localAttackers']} attackers vs {evidence['localDefenders']} defenders within 15m."
        if kind == "dangerous_run":
            return "Observed forward run beyond the second-deepest visible defender; not an offside judgment."
        if kind == "final_third_entry":
            return "Controlled ball position in the attacking third under the configured attack direction."
        return "Sustained possession estimate from ball proximity and recent observations."

    def for_judge(self, frame):
        t = frame["time"]
        recent = list(self.history)[-15:]
        return {
            "sport": "association football",
            "tacticalReference": self.knowledge,
            "reconstructionUsesFutureObservations": True,
            "forecastHorizonSeconds": 3,
            "timeSeconds": t,
            "coordinateSystem": "105x68 meter pitch; automatically estimated geometry",
            "observationsArePartial": True,
            "attackDirectionIsConfiguredNotVerified": True,
            "current": frame["state"],
            "calibration": frame["calibration"],
            "ball": frame["ball"],
            "players": [
                {
                    "id": p["id"],
                    "team": p["team"],
                    "xMeters": round(p["x"] * 1.05, 1),
                    "yMeters": round(p["y"] * 0.68, 1),
                    "speedMps": p.get("speedMps"),
                    "observationConfidence": round(p["confidence"], 2),
                    "teamConfidence": p["teamConfidence"],
                }
                for p in frame["players"]
                if p["team"] != "unknown"
            ]
            if frame["calibration"]["valid"]
            else [],
            "history": [
                {
                    "t": f["time"],
                    "possession": f["state"]["possession"],
                    "ball": {
                        "x": round(f["ball"]["x"], 1),
                        "y": round(f["ball"]["y"], 1),
                        "status": f["ball"]["status"],
                    }
                    if f["ball"] and f["calibration"]["valid"]
                    else None,
                    "phase": f["state"]["phase"],
                    "context": f["state"].get("context"),
                }
                for f in recent[::2]
            ],
            "unknowns": [
                "off-camera players",
                "jersey identities",
                "intent",
                "whether ball is airborne",
                "true pitch dimensions",
            ],
        }
