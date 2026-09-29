import { memo } from 'react';
import type { Analysis } from '../core/model';
import { humanize, judgmentAt } from '../core/pipeline';

export default memo(function ActionOverlay({
  analysis,
  time,
}: {
  analysis: Analysis;
  time: number;
}) {
  const judgment = judgmentAt(analysis, time);
  const stale =
    !judgment ||
    time - judgment.time > 3 ||
    analysis.frames.some((f) => f.calibration?.cut && f.time > judgment.time && f.time <= time);
  const leading =
    judgment?.source === 'jev' && !stale
      ? Object.entries(judgment.nextAction?.probabilities ?? {}).sort((a, b) => b[1] - a[1])[0]
      : undefined;
  const label = leading
    ? leading[0] === 'insufficient_evidence'
      ? 'Read uncertain'
      : humanize(leading[0])
    : 'No current prediction';
  return (
    <div
      className={`action-overlay ${leading ? '' : 'unavailable'}`}
      aria-label="Most likely next action"
    >
      <div className="action-overlay-caption">JEV · MOST LIKELY NEXT ACTION</div>
      <div className="action-overlay-value" key={label}>
        <strong>{label}</strong>
        {leading && (
          <span>
            {Math.round(leading[1] * 100)}
            <small>%</small>
          </span>
        )}
      </div>
      <div className="action-overlay-meter">
        <i style={{ transform: `scaleX(${leading?.[1] ?? 0})` }} />
      </div>
      <div className="action-overlay-detail">
        {leading
          ? `3-second forecast · judged at ${judgment!.time.toFixed(1)}s`
          : 'Awaiting supported evidence'}
      </div>
    </div>
  );
});
