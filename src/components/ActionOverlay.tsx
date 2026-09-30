import { memo } from 'react';
import type { Analysis } from '../core/model';
import { decisionAt } from '../core/pipeline';

export default memo(function ActionOverlay({
  analysis,
  time,
}: {
  analysis: Analysis;
  time: number;
}) {
  const view = decisionAt(analysis, time);
  const leading = view.ranked[0];
  const label = view.label;
  const control = view.frame?.state?.ballControl;
  return (
    <div
      className={`action-overlay ${leading ? '' : 'unavailable'}`}
      aria-label="Most likely next action"
    >
      {control && (
        <div className="action-overlay-now">
          <span>NOW</span> {control.label}
        </div>
      )}
      <div className="action-overlay-caption">JEV · NEXT</div>
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
          ? `Track IDs · read at ${view.judgment!.time.toFixed(1)}s`
          : 'Awaiting supported evidence'}
      </div>
    </div>
  );
});
