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
