"""Ball lifecycle and concrete, visible-player action candidates for Level 2 replay.

Transit is a motion hypothesis, not a claim that a planar detector measures ball height.
No future reception label is used to select a predicted recipient.
"""

from collections import deque
import numpy as np


def point(p):
    return np.array([p["x"] * 1.05, p["y"] * 0.68])


class BallControl:
    def __init__(self):
        self.previous = None
        self.motion = deque(maxlen=4)
        self.actor = None
        self.team = None
        self.last_control = -10.0
        self.candidate = None
        self.candidate_since = 0.0
        self.phase = "unknown"
        self.epoch = 0
        self.signature = None
        self.shot = None
        self.received_at = -10.0

    def update(self, frame):
        t = frame["time"]
        ball = frame.get("ball")
        shot = frame["calibration"]["shot"]
        if shot != self.shot:
            self.actor = None
            self.team = None
            self.previous = None
            self.motion.clear()
            self.last_control = -10.0
            self.candidate = None
            self.phase = "unknown"
            self.shot = shot
        players = [
            p
            for p in frame["players"]
            if p["team"] in ("home", "away") and p.get("role") != "referee"
        ]
        valid = bool(ball and frame["calibration"]["valid"] and ball.get("confidence", 0) >= 0.15)
        velocity = None
        speed = None
        if valid:
            if self.motion and t - self.motion[-1][0] > 0.4:
                self.motion.clear()
            self.motion.append((t, point(ball)))
            if len(self.motion) >= 2:
                times = np.array([sample[0] for sample in self.motion])
                times -= times.mean()
                points = np.array([sample[1] for sample in self.motion])
                velocity = (times[:, None] * (points - points.mean(axis=0))).sum(axis=0) / max(
                    float(np.dot(times, times)), 0.001
                )
                speed = float(np.linalg.norm(velocity))
                if speed > 45:
                    velocity = None
                    speed = None
        else:
            self.motion.clear()
        ranked = (
            sorted([(float(np.linalg.norm(point(p) - point(ball))), p["id"], p) for p in players])
            if valid
            else []
        )
        nearest = ranked[0][2] if ranked else None
        control_speed = None
        if len(self.motion) >= 2:
            dt = self.motion[-1][0] - self.motion[-2][0]
            control_speed = float(np.linalg.norm(self.motion[-1][1] - self.motion[-2][1])) / max(
                dt, 0.001
            )
        controlled = bool(
            ranked and ranked[0][0] < 2.8 and (control_speed is None or control_speed < 10)
        )
        contested = bool(
            ranked
            and len(ranked) > 1
            and ranked[0][0] < 3
            and ranked[1][0] < 3
            and ranked[0][2]["team"] != ranked[1][2]["team"]
        )
        previous_phase = self.phase
        if not valid:
            phase = "unknown"
            self.candidate = None
        elif not -1 <= ball["x"] <= 101 or not -1 <= ball["y"] <= 101:
            phase = "out_of_play"
            self.candidate = None
        elif contested:
            phase = "contested"
            self.candidate = None
        elif controlled:
            if self.candidate != nearest["id"]:
                self.candidate = nearest["id"]
                self.candidate_since = t
            if (
                self.actor == nearest["id"]
                and t - self.last_control <= 0.6
                or t - self.candidate_since >= 0.19
            ):
                if previous_phase in ("released", "in_transit") or (
                    self.actor is not None and self.actor != nearest["id"]
                ):
                    self.received_at = t
                self.actor = nearest["id"]
                self.team = nearest["team"]
                self.last_control = t
                phase = "reception" if t - self.received_at < 0.4 else "controlled"
            else:
                phase = (
                    "in_transit"
                    if previous_phase in ("released", "in_transit")
                    else "uncertain_control"
                )
        else:
            self.candidate = None
            if self.actor is not None and t - self.last_control <= 3:
                phase = (
                    "released" if previous_phase in ("controlled", "reception") else "in_transit"
                )
            elif speed is not None and speed > 5:
                phase = "in_transit"
            else:
                phase = "loose_ball"
        if t - self.last_control > 3:
            self.actor = None
            self.team = None
        actor = self.actor if phase in ("controlled", "reception") else None
        # Every possession/flight boundary invalidates the previous decision immediately.
        signature = (shot, phase, actor)
        if signature != self.signature:
            self.epoch += 1
            self.signature = signature
        receivers = []
        if (
            valid
            and phase in ("released", "in_transit")
            and velocity is not None
            and np.linalg.norm(velocity) > 1
        ):
            for p in players:
                if p["id"] == self.actor:
                    continue
                delta = point(p) - point(ball)
                arrival = float(np.dot(delta, velocity) / max(1, np.dot(velocity, velocity)))
                miss = float(np.linalg.norm(delta - velocity * np.clip(arrival, 0, 1.5)))
                if -0.1 < arrival < 1.5 and miss < 8:
                    receivers.append(
                        {
                            "id": p["id"],
                            "team": p["team"],
                            "arrivalSeconds": round(max(0, arrival), 2),
                            "pathDistanceMeters": round(miss, 2),
                        }
                    )
            receivers = sorted(
                receivers, key=lambda r: r["pathDistanceMeters"] + r["arrivalSeconds"]
            )[:3]
        if actor is not None:
            label = f"#{actor} receiving" if phase == "reception" else f"#{actor} on the ball"
        elif phase == "released":
            label = f"Ball released by #{self.actor}"
        elif phase == "in_transit":
            label = "Ball in transit"
        elif phase == "contested":
            label = "Contested ball"
        elif phase == "out_of_play":
            label = "Ball outside pitch estimate"
        elif phase == "uncertain_control":
            label = f"Possible control · #{nearest['id']}"
        else:
            label = "Ball control unresolved"
        self.phase = phase
        self.previous = frame
        return {
            "phase": phase,
            "epoch": self.epoch,
            "actorId": actor,
            "team": self.team,
            "lastActorId": self.actor,
            "lastControlAgeSeconds": round(t - self.last_control, 2)
            if self.actor is not None
            else None,
            "receiverCandidates": receivers,
            "speedMps": round(speed, 2) if speed is not None else None,
            "label": label,
            "confidence": round(min(ball.get("confidence", 0), 0.85 if actor else 0.6), 2)
            if valid
            else 0,
            "heightKnown": False,
        }


def action_candidates(frame):
    state = frame["state"]
    control = state["ballControl"]
    actor = control["actorId"]
    players = {p["id"]: p for p in frame["players"] if p.get("role") != "referee"}
    result = []

    def add(key, kind, label, target=None, **evidence):
        result.append(
            {
                "id": key,
                "kind": kind,
                "label": label,
                "actorId": actor,
                "targetId": target,
                "evidence": evidence,
            }
        )

    if actor in players and control["phase"] in ("controlled", "reception"):
        carrier = players[actor]
        team = carrier["team"]
        direction = 1 if (team == "home") == state["homeAttacksRight"] else -1
        opponents = [p for p in players.values() if p["team"] not in (team, "unknown")]
        options = []
        for p in players.values():
            if p["id"] == actor or p["team"] != team:
                continue
            delta = point(p) - point(carrier)
            distance = float(np.linalg.norm(delta))
            if not 3 < distance < 45:
                continue
            blocked = False
            for defender in opponents:
                offset = point(defender) - point(carrier)
                u = float(np.dot(offset, delta) / (distance * distance))
                if 0 < u < 1 and np.linalg.norm(offset - u * delta) < 1.8:
                    blocked = True
            options.append(
                (int(blocked) * 25 + distance - 0.2 * delta[0] * direction, p, distance, blocked)
            )
        for _, p, distance, blocked in sorted(options, key=lambda o: o[0])[:4]:
            add(
                f"pass_{actor}_{p['id']}",
                "pass",
                f"#{actor} → #{p['id']} pass",
                p["id"],
                distanceMeters=round(distance, 1),
                laneBlocked=blocked,
            )
        add(f"carry_{actor}", "carry", f"#{actor} carries forward")
        context = state.get("context", {})
        if context.get("crossingTerritory"):
            for target in context.get("boxTargetIds", [])[:2]:
                add(
                    f"cross_{actor}_{target}",
                    "cross",
                    f"#{actor} → #{target} cross",
                    target,
                    boxArrivals=context.get("boxEnteringRunIds", []),
                )
        if context.get("centralShootingZone") or context.get("distanceToGoalLineMeters", 105) < 25:
            add(f"shot_{actor}", "shot", f"#{actor} shoots")
        add(f"turnover_{actor}", "turnover", f"#{actor} loses possession")
        add(f"other_pass_{actor}", "pass", f"#{actor} passes · other target")
    elif control["phase"] in ("released", "in_transit"):
        for receiver in control["receiverCandidates"]:
            kind = (
                "receive"
                if receiver["team"] == control["team"] or control["team"] is None
                else "turnover"
            )
            add(
                f"receive_{receiver['id']}",
                kind,
                f"#{receiver['id']} " + ("receives" if kind == "receive" else "intercepts"),
                receiver["id"],
                **receiver,
            )
        add("unresolved_reception", "receive", "Reception · target unresolved")
        add("transit_stoppage", "stoppage", "Ball leaves play")
    elif control["phase"] == "out_of_play":
        add("stoppage", "stoppage", "Play stops")
    elif control["phase"] in ("loose_ball", "contested", "uncertain_control"):
        if frame.get("ball"):
            nearby = sorted(
                players.values(), key=lambda p: np.linalg.norm(point(p) - point(frame["ball"]))
            )[:3]
            for p in nearby:
                if p["team"] != "unknown" and np.linalg.norm(point(p) - point(frame["ball"])) < 6:
                    add(f"control_{p['id']}", "receive", f"#{p['id']} gains control", p["id"])
    add("insufficient_evidence", "insufficient_evidence", "Read uncertain")
    # Explicit alternative prevents a one-choice API request without inventing an actor.
    if len(result) == 1:
        add("unresolved_control", "receive", "Next control unresolved")
    return result
