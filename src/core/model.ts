import type { Judgment, PipelineState } from './pipeline';
export type Team = 'home' | 'away' | 'unknown';
export interface Point {
  x: number;
  y: number;
}
export interface Player extends Point {
  id: number;
  team: Team;
  confidence: number;
  teamConfidence?: number;
  image?: Point;
  box?: number[];
  role?: string;
  speedMps?: number | null;
  distanceMeters?: number | null;
}
export interface Ball extends Point {
  image?: Point;
  confidence?: number;
  status?: 'observed' | 'predicted';
}
export interface Frame {
  time: number;
  players: Player[];
  ball: Ball | null;
  coordinateSpace?: 'pitch' | 'image';
  calibration?: {
    valid: boolean;
    confidence?: number;
    shot: number;
    cut?: boolean;
    method?: string;
    reprojectionErrorMeters?: number;
    landmarks?: number;
    inliers?: number;
  };
  state?: PipelineState;
}
export interface Event {
  time: number;
  kind: string;
  detail: string;
  confidence: number;
}
export interface Analysis {
  frames: Frame[];
  duration: number;
  events: Event[];
  source: 'simulation' | 'local' | 'pipeline';
  judgments?: Judgment[];
  videoUrl?: string;
  sampleFps?: number;
  quality?: {
    frames: number;
    uniqueTracks: number;
    ballObservedFraction: number;
    ballPredictedFraction: number;
    calibratedFraction: number;
    possessionKnownFraction: number;
    processingSeconds: number;
    jevResponses: number;
  };
  name: string;
}
export const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
export function frameAt(frames: Frame[], time: number): Frame {
  if (!frames.length) return { time, players: [], ball: null };
  let lo = 0,
    hi = frames.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (frames[mid].time <= time) lo = mid;
    else hi = mid - 1;
  }
  const a = frames[lo],
    b = frames[Math.min(lo + 1, frames.length - 1)];
  const ratio =
    a.coordinateSpace !== b.coordinateSpace || a.calibration?.shot !== b.calibration?.shot
      ? 0
      : Math.max(0, Math.min(1, (time - a.time) / (b.time - a.time || 1)));
  const blend = (p: Point, q: Point): Point => ({
    x: p.x + (q.x - p.x) * ratio,
    y: p.y + (q.y - p.y) * ratio,
  });
  return {
    ...a,
    time,
    players: a.players.map((p) => {
      const q = b.players.find((x) => x.id === p.id);
      return q ? { ...p, ...blend(p, q) } : p;
    }),
    ball: a.ball && b.ball ? { ...a.ball, ...blend(a.ball, b.ball) } : a.ball,
  };
}
export function stateAt(frames: Frame[], time: number) {
  const frame = frameAt(frames, time),
    prior = frameAt(frames, Math.max(0, time - 1));
  const nearest = frame.ball
    ? [...frame.players].sort((a, b) => distance(a, frame.ball!) - distance(b, frame.ball!))[0]
    : undefined;
  const owner = nearest && distance(nearest, frame.ball!) < 8 ? nearest : undefined;
  const home = frame.players.filter((p) => p.team === 'home');
  const width =
    home.length > 1 ? Math.max(...home.map((p) => p.y)) - Math.min(...home.map((p) => p.y)) : 0;
  const depth =
    home.length > 1 ? Math.max(...home.map((p) => p.x)) - Math.min(...home.map((p) => p.x)) : 0;
  const pressure = owner
    ? frame.players.filter((p) => p.team !== owner.team && distance(p, owner) < 12).length
    : 0;
  const advance = frame.ball && prior.ball ? frame.ball.x - prior.ball.x : 0;
  const phase = !owner
    ? 'Uncertain possession'
    : pressure >= 2
      ? 'Under pressure'
      : advance > 2.2 && owner.team === 'home'
        ? 'Quick progression'
        : frame.ball!.x > 70 && owner.team === 'home'
          ? 'Final-third entry'
          : 'Building possession';
  if (frame.state)
    return {
      frame,
      owner: frame.players.find((p) => p.id === frame.state!.carrierId),
      width: (frame.state.teams.home.widthMeters ?? 0) / 0.68,
      depth: (frame.state.teams.home.depthMeters ?? 0) / 1.05,
      pressure: frame.state.evidence.pressureCount,
      advance: frame.state.evidence.forwardProgressMps ?? 0,
      phase: frame.state.phase.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase()),
    };
  return { frame, owner, width, depth, pressure, advance, phase };
}
// Stateful event suppression: a signal must persist for 0.5s; recurring events cool down for 4s.
export function detectEvents(frames: Frame[]): Event[] {
  const events: Event[] = [];
  let candidate = '',
    since = 0,
    emitted = '';
  const last = new Map<string, number>();
  for (const frame of frames) {
    const state = stateAt(frames, frame.time);
    if (state.phase !== candidate) {
      candidate = state.phase;
      since = frame.time;
      emitted = '';
    }
    if (
      frame.time - since < 0.5 ||
      emitted === candidate ||
      frame.time - (last.get(candidate) ?? -10) < 4 ||
      !state.owner
    )
      continue;
    emitted = candidate;
    last.set(candidate, frame.time);
    events.push({
      time: since,
      kind: candidate,
      confidence: Math.min(0.88, state.owner.confidence),
      detail:
        candidate === 'Under pressure'
          ? `${state.pressure} opponents are within 12 pitch units of the ball carrier.`
          : candidate === 'Quick progression'
            ? 'The ball is advancing toward the right goal with a nearby home player.'
            : candidate === 'Final-third entry'
              ? 'Home possession has moved beyond the final-third boundary.'
              : 'A nearby player supports the current possession estimate.',
    });
  }
  return events;
}
export function playerMetrics(frames: Frame[], id: number, time: number) {
  const current = frameAt(frames, time).players.find((p) => p.id === id);
  if (frames[0]?.state)
    return { distance: current?.distanceMeters ?? 0, speed: (current?.speedMps ?? 0) * 3.6 };
  let total = 0,
    speed = 0;
  for (let i = 1; i < frames.length && frames[i].time <= time; i++) {
    const a = frames[i - 1].players.find((p) => p.id === id),
      b = frames[i].players.find((p) => p.id === id);
    if (a && b) {
      const d = Math.hypot((b.x - a.x) * 1.05, (b.y - a.y) * 0.68);
      total += d;
      speed = (d / Math.max(0.001, frames[i].time - frames[i - 1].time)) * 3.6;
    }
  }
  return { distance: total, speed };
}
