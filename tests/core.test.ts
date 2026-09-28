import { describe, expect, it } from 'vitest';
import { frameAt, stateAt, detectEvents, playerMetrics, type Frame } from '../src/core/model';
import { Tracker, detectKits } from '../src/core/tracker';
import { createDemo } from '../src/core/demo';
const frame = (time: number, x: number, ball = true): Frame => ({
  time,
  players: [{ id: 1, team: 'home', x, y: 50, confidence: 0.8 }],
  ball: ball ? { x: x + 1, y: 50 } : null,
});
describe('temporal state', () => {
  it('interpolates and clamps replay coordinates', () => {
    const frames = [frame(0, 10), frame(2, 20)];
    expect(frameAt(frames, 1).players[0].x).toBe(15);
    expect(frameAt(frames, -1).players[0].x).toBe(10);
    expect(frameAt(frames, 9).players[0].x).toBe(20);
  });
  it('abstains without ball evidence', () => {
    const frames = [frame(0, 10, false), frame(1, 15, false)];
    expect(stateAt(frames, 1).owner).toBeUndefined();
    expect(detectEvents(frames)).toEqual([]);
  });
  it('abstains when the ball is far from all players', () => {
    const f = frame(0, 10);
    f.ball = { x: 90, y: 50 };
    expect(stateAt([f], 0).owner).toBeUndefined();
  });
  it('requires sustained evidence before emitting an event', () => {
    expect(detectEvents([frame(0, 10), frame(0.2, 10)])).toEqual([]);
    expect(detectEvents([frame(0, 10), frame(0.6, 10)])).toHaveLength(1);
  });
  it('does not duplicate a persistent event', () =>
    expect(detectEvents(Array.from({ length: 30 }, (_, i) => frame(i, 10)))).toHaveLength(1));
  it('does not use future frames for event decisions', () => {
    const demo = createDemo();
    const prefix = demo.frames.filter((f) => f.time <= 8);
    expect(detectEvents(prefix)).toEqual(demo.events.filter((e) => e.time <= 7.5));
  });
  it('computes distance in meters for a calibrated pitch', () => {
    expect(playerMetrics([frame(0, 10), frame(1, 20)], 1, 1).distance).toBeCloseTo(10.5);
    expect(playerMetrics([frame(0, 10), frame(1, 20)], 1, 0).distance).toBe(0);
  });
  it('handles an empty frame stream', () =>
    expect(stateAt([], 2).phase).toBe('Uncertain possession'));
});
describe('local tracking', () => {
  it('keeps IDs through motion and a brief occlusion, but expires stale identities', () => {
    const t = new Tracker();
    const d = { x: 20, y: 30, team: 'home' as const, confidence: 0.45 };
    const first = t.update([d], 0)[0].id;
    expect(t.update([{ ...d, x: 22 }], 0.2)[0].id).toBe(first);
    t.update([], 0.4);
    expect(t.update([d], 0.6)[0].id).toBe(first);
    expect(t.update([d], 2)[0].id).not.toBe(first);
  });
  it('does not match across teams or assign one ID twice', () => {
    const t = new Tracker();
    const d = { x: 20, y: 30, team: 'home' as const, confidence: 0.45 };
    const a = t.update([d], 0)[0];
    const b = t.update([{ ...d, team: 'away' }, d, { ...d, x: 21 }], 0.2);
    expect(b[0].id).not.toBe(a.id);
    expect(new Set(b.map((x) => x.id)).size).toBe(3);
  });
  it('extracts kit blobs and rejects empty green frames', () => {
    const w = 100,
      h = 100,
      data = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) {
      data[i * 4 + 1] = 120;
      data[i * 4 + 3] = 255;
    }
    expect(detectKits(data, w, h)).toEqual([]);
    for (let y = 40; y < 47; y++)
      for (let x = 20; x < 24; x++) {
        data[(y * w + x) * 4] = 200;
        data[(y * w + x) * 4 + 1] = 20;
      }
    const d = detectKits(data, w, h);
    expect(d).toHaveLength(1);
    expect(d[0].team).toBe('home');
  });
});

import { homography, project, enrichFrames } from '../src/core/geometry';
describe('assisted calibration', () => {
  it('maps a perspective quadrilateral to normalized pitch corners', () => {
    const points = [
      { x: 20, y: 20 },
      { x: 80, y: 20 },
      { x: 95, y: 90 },
      { x: 5, y: 90 },
    ];
    const m = homography(points);
    const expected = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
      { x: 100, y: 100 },
      { x: 0, y: 100 },
    ];
    points.forEach((p, i) => {
      expect(project(p, m).x).toBeCloseTo(expected[i].x);
      expect(project(p, m).y).toBeCloseTo(expected[i].y);
    });
  });
  it('rejects crossed or degenerate corner sequences', () => {
    expect(() =>
      homography([
        { x: 0, y: 0 },
        { x: 100, y: 100 },
        { x: 100, y: 0 },
        { x: 0, y: 100 },
      ]),
    ).toThrow();
    expect(() => homography(Array(4).fill({ x: 0, y: 0 }))).toThrow();
  });
  it('interpolates only between nearby ball annotations and preserves unknown gaps', () => {
    const frames = [
      frame(0, 10, false),
      frame(1, 10, false),
      frame(2, 10, false),
      frame(3, 10, false),
      frame(5, 10, false),
    ];
    const enriched = enrichFrames(frames, null, [
      { time: 0, x: 10, y: 50 },
      { time: 2, x: 20, y: 50 },
      { time: 5, x: 90, y: 50 },
    ]);
    expect(enriched[1].ball?.x).toBe(15);
    expect(enriched[3].ball).toBeNull();
    expect(enriched[4].ball?.x).toBe(90);
  });
});
