import type { Frame, Point } from './model';
export type Matrix = number[];
// Four point correspondences determine the eight free parameters of a planar homography.
export function homography(corners: Point[]): Matrix {
  if (corners.length !== 4) throw new Error('Mark all four corners.');
  const cross = (a: Point, b: Point, c: Point) =>
    (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
  const turns = corners.map((p, i) => cross(p, corners[(i + 1) % 4], corners[(i + 2) % 4]));
  if (
    turns.some((t) => Math.abs(t) < 1) ||
    !turns.every((t) => Math.sign(t) === Math.sign(turns[0]))
  )
    throw new Error('Choose four distinct corners in clockwise order around the pitch.');
  const target = [
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    { x: 100, y: 100 },
    { x: 0, y: 100 },
  ];
  const rows: number[][] = [];
  corners.forEach(({ x, y }, i) => {
    const { x: u, y: v } = target[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u], [0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  });
  for (let col = 0; col < 8; col++) {
    let pivot = col;
    for (let r = col + 1; r < 8; r++)
      if (Math.abs(rows[r][col]) > Math.abs(rows[pivot][col])) pivot = r;
    if (Math.abs(rows[pivot][col]) < 1e-8)
      throw new Error('These corners cannot define a stable pitch projection.');
    [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
    const divisor = rows[col][col];
    rows[col] = rows[col].map((n) => n / divisor);
    for (let r = 0; r < 8; r++)
      if (r !== col) {
        const factor = rows[r][col];
        rows[r] = rows[r].map((n, i) => n - factor * rows[col][i]);
      }
  }
  return [...rows.map((r) => r[8]), 1];
}
export function project(p: Point, m: Matrix): Point {
  const d = m[6] * p.x + m[7] * p.y + m[8];
  if (Math.abs(d) < 1e-8) return { x: NaN, y: NaN };
  return { x: (m[0] * p.x + m[1] * p.y + m[2]) / d, y: (m[3] * p.x + m[4] * p.y + m[5]) / d };
}
export interface BallMark extends Point {
  time: number;
}
export function enrichFrames(frames: Frame[], matrix: Matrix | null, marks: BallMark[]): Frame[] {
  const sorted = [...marks].sort((a, b) => a.time - b.time);
  return frames.map((f) => {
    const before = sorted.filter((m) => m.time <= f.time + 0.001).at(-1),
      after = sorted.find((m) => m.time >= f.time - 0.001);
    let ball: Point | null = null;
    if (before && after && after.time - before.time <= 2) {
      const ratio = (f.time - before.time) / (after.time - before.time || 1);
      ball = {
        x: before.x + (after.x - before.x) * ratio,
        y: before.y + (after.y - before.y) * ratio,
      };
    }
    const players = matrix
      ? f.players
          .map((p) => ({ ...p, ...project(p, matrix) }))
          .filter(
            (p) =>
              Number.isFinite(p.x) &&
              Number.isFinite(p.y) &&
              p.x >= 0 &&
              p.x <= 100 &&
              p.y >= 0 &&
              p.y <= 100,
          )
      : f.players;
    const mappedBall = ball && matrix ? project(ball, matrix) : ball;
    const validBall =
      mappedBall &&
      Number.isFinite(mappedBall.x) &&
      Number.isFinite(mappedBall.y) &&
      mappedBall.x >= 0 &&
      mappedBall.x <= 100 &&
      mappedBall.y >= 0 &&
      mappedBall.y <= 100
        ? mappedBall
        : null;
    return { ...f, players, ball: validBall };
  });
}

/** Monotone-chain hull: team envelope must not self-intersect or depend on player order. */
export function convexHull(points: Point[]): Point[] {
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  if (sorted.length < 3) return sorted;
  const turn = (a: Point, b: Point, c: Point) =>
    (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const half = (items: Point[]) => {
    const hull: Point[] = [];
    for (const p of items) {
      while (hull.length >= 2 && turn(hull[hull.length - 2], hull[hull.length - 1], p) <= 0)
        hull.pop();
      hull.push(p);
    }
    return hull;
  };
  const lower = half(sorted),
    upper = half([...sorted].reverse());
  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}
