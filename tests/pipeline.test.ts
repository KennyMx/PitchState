import { expect, it } from 'vitest';
import { frameAt, type Frame, type Analysis } from '../src/core/model';
import { judgmentAt } from '../src/core/pipeline';

it('preserves provenance and does not interpolate across camera shots', () => {
  const frames: Frame[] = [
    {
      time: 0,
      players: [{ id: 1, team: 'home', confidence: 0.9, x: 10, y: 20 }],
      ball: { x: 10, y: 20, status: 'observed', confidence: 0.8 },
      calibration: { valid: true, shot: 0 },
      coordinateSpace: 'pitch',
    },
    {
      time: 1,
      players: [{ id: 1, team: 'home', confidence: 0.9, x: 90, y: 20 }],
      ball: { x: 90, y: 20, status: 'observed' },
      calibration: { valid: true, shot: 1 },
      coordinateSpace: 'pitch',
    },
  ];
  const frame = frameAt(frames, 0.5);
  expect(frame.players[0].x).toBe(10);
  expect(frame.ball?.confidence).toBe(0.8);
  expect(frame.calibration?.shot).toBe(0);
});
it('never displays a future Jev judgment when seeking backward', () => {
  const analysis: Analysis = {
    name: 'test',
    source: 'pipeline',
    duration: 4,
    frames: [],
    events: [],
    judgments: [
      { time: 0, source: 'unavailable', reason: 'missing' },
      {
        time: 3,
        source: 'jev',
        nextAction: { choice: 'pass', confidence: 0.8, probabilities: { pass: 1 } },
      },
    ],
  };
  expect(judgmentAt(analysis, 2)?.source).toBe('unavailable');
  expect(judgmentAt(analysis, 3)?.nextAction?.choice).toBe('pass');
});

it('interpolates image boxes and ball at a 60Hz replay cadence from 5Hz observations', () => {
  const frames: Frame[] = [0, 0.2].map((time) => ({
    time,
    players: [
      {
        id: 1,
        team: 'home',
        confidence: 0.9,
        x: time * 10,
        y: 20,
        box: [time * 600, 0, 40 + time * 600, 80],
        image: { x: time * 60, y: 50 },
      },
    ],
    ball: { x: time * 10, y: 20, image: { x: time * 60, y: 50 }, status: 'observed' },
    calibration: { valid: true, shot: 0 },
    coordinateSpace: 'pitch',
  }));
  for (let i = 0; i <= 12; i++) {
    const f = frameAt(frames, i / 60);
    expect(f.players[0].box![0]).toBeCloseTo(i * 10);
    expect(f.ball!.image!.x).toBeCloseTo(i);
  }
});

it('invalidates a specific pass on release and never carries it into flight', async () => {
  const { decisionAt } = await import('../src/core/pipeline');
  const a = {
    name: 'level2',
    source: 'pipeline',
    duration: 1,
    events: [],
    frames: [
      { time: 0, players: [], ball: null, state: { ballControl: { epoch: 1 } } },
      { time: 0.2, players: [], ball: null, state: { ballControl: { epoch: 2 } } },
    ],
    judgments: [
      {
        time: 0,
        source: 'jev',
        controlEpoch: 1,
        validUntil: 0.4,
        nextDecision: {
          choice: 'pass_1_2',
          confidence: 0.7,
          probabilities: { pass_1_2: 0.8, carry_1: 0.2 },
        },
        candidates: [
          { id: 'pass_1_2', kind: 'pass', label: '#1 → #2 pass', actorId: 1, targetId: 2 },
        ],
      },
    ],
  } as unknown as Analysis;
  expect(decisionAt(a, 0.1).candidate?.targetId).toBe(2);
  expect(decisionAt(a, 0.2).candidate).toBeUndefined();
  expect(decisionAt(a, 0.5).valid).toBe(false);
});
