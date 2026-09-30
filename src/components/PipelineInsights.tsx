import { memo } from 'react';
import { Activity, BrainCircuit, Eye, Radio, ShieldCheck } from 'lucide-react';
import type { Analysis } from '../core/model';
import { humanize, decisionAt } from '../core/pipeline';
function PipelineInsights({
  analysis,
  time,
  onSeek,
}: {
  analysis: Analysis;
  time: number;
  onSeek: (time: number) => void;
}) {
  const view = decisionAt(analysis, time),
    judgment = view.judgment,
    frame = view.frame,
    s = frame?.state,
    q = analysis.quality;
  const stale = !view.valid;
  const probabilities = view.ranked;
  const labelFor = (id: string) =>
    judgment?.candidates?.find((c) => c.id === id)?.label ?? humanize(id);
  const ticks = analysis.judgments?.filter(
    (_j, i, all) => i % Math.max(1, Math.ceil(all.length / 16)) === 0 || i === all.length - 1,
  );
  return (
    <section className="pipeline-insights">
      <div className="pipeline-path">
        <span>
          <Eye size={14} /> Neural perception
        </span>
        <i>→</i>
        <span>
          <Activity size={14} /> Game state
        </span>
        <i>→</i>
        <span>Tactical evidence</span>
        <i>→</i>
        <span className="jev-label">
          <BrainCircuit size={14} /> Jev
        </span>
        <i>→</i>
        <span>Next-action probabilities</span>
      </div>
      <div className="forecast-grid">
        <section className="forecast">
          <div className="card-heading">
            <h2>
              <BrainCircuit size={16} /> What happens next?
            </h2>
            <span className="tag">NEXT 3 SECONDS</span>
          </div>
          {probabilities.length ? (
            <>
              <div className="forecast-head">
                <strong>{view.label}</strong>
                <span>
                  {stale
                    ? 'STALE · RE-EVALUATION NEEDED'
                    : `${Math.round((judgment!.nextAction!.confidence ?? 0) * 100)}% model confidence`}
                </span>
              </div>
              <div className={`probability-bars ${stale ? 'stale' : ''}`}>
                {probabilities.map(([name, value]) => (
                  <div className="probability" key={name}>
                    <span>{labelFor(name)}</span>
                    <div>
                      <i style={{ width: `${value * 100}%` }} />
                    </div>
                    <b>{(value * 100).toFixed(1)}%</b>
                  </div>
                ))}
              </div>
              <div className="forecast-note">
                {judgment!.model} · judged at {judgment!.time.toFixed(1)}s · {judgment!.latencyMs}{' '}
                ms {judgment!.cached ? '· cached' : ''}
                <br />
                Precomputed every analysis frame. Numbers identify tracks, not jersey numbers.
              </div>
            </>
          ) : (
            <div className="forecast-empty">
              {judgment?.reason ?? 'Waiting for a Jev judgment at this point in the clip.'}
            </div>
          )}
        </section>
        <section className="evidence-panel">
          <div className="card-heading">
            <h2>
              <Radio size={16} /> The evolving read
            </h2>
            <span className="tiny">{time.toFixed(1)}s</span>
          </div>
          <div className="phase-read">
            <span>JEV TACTICAL PHASE</span>
            <strong>
              {judgment?.phase ? humanize(judgment.phase.choice) : 'Awaiting judgment'}
            </strong>
            <small>State-rule baseline: {humanize(s?.phase ?? 'unknown')}</small>
          </div>
          {s?.ballControl && (
            <div className="control-read">
              <span>HAPPENING NOW</span>
              <strong>{s.ballControl.label}</strong>
              <small>
                Track IDs · control confidence {Math.round(s.ballControl.confidence * 100)}%
              </small>
            </div>
          )}
          <dl>
            <div>
              <dt>Possession</dt>
              <dd>
                {s?.possession === 'home'
                  ? 'Team A'
                  : s?.possession === 'away'
                    ? 'Team B'
                    : 'Unknown'}{' '}
                {s?.carrierId ? `· #${s.carrierId}` : ''}
              </dd>
            </div>
            <div>
              <dt>Ball evidence</dt>
              <dd>
                {frame.ball
                  ? `${frame.ball.status} · ${Math.round((frame.ball.confidence ?? 0) * 100)}%`
                  : 'Not visible'}
              </dd>
            </div>
            <div>
              <dt>Pressure / pass options</dt>
              <dd>
                {s?.evidence.pressureCount ?? 0} opponents /{' '}
                {s?.evidence.openPassOptions.length ?? 0} options
              </dd>
            </div>
            <div>
              <dt>Local numbers</dt>
              <dd>
                {s?.evidence.localAttackers ?? 0} v {s?.evidence.localDefenders ?? 0}
                {s?.evidence.overload ? ' · overload' : ''}
              </dd>
            </div>
            <div>
              <dt>Pitch calibration</dt>
              <dd>
                {frame.calibration?.valid
                  ? `${frame.calibration.inliers ?? '—'} landmarks · ${Math.round((frame.calibration.confidence ?? 0) * 100)}%`
                  : 'Unavailable'}
              </dd>
            </div>
            {s?.context && (
              <div>
                <dt>Attacking context</dt>
                <dd>
                  {s.context.canReason
                    ? `${s.context.attackingTeam === 'home' ? 'Team A' : 'Team B'} · ${humanize(s.context.contextSource)}`
                    : 'Unresolved'}
                </dd>
              </div>
            )}
            {s?.context?.crossingTerritory && (
              <div>
                <dt>Crossing situation</dt>
                <dd>
                  {s.context.boxTargetIds?.length ?? 0} box targets ·{' '}
                  {s.context.boxEnteringRunIds?.length ?? 0} arriving runs
                </dd>
              </div>
            )}
          </dl>
          <div className="judgment-ticks">
            {ticks?.map((j, i) => (
              <button
                key={i}
                className={j.time <= time ? 'past' : ''}
                title={`Jev at ${j.time}s`}
                onClick={() => onSeek(j.time)}
              >
                {j.time.toFixed(1)}s
              </button>
            ))}
          </div>
          <p className="forecast-note">
            <ShieldCheck size={12} /> Short gaps may be reconstructed; long gaps stay unknown.
            Direction: Team A attacks {s?.homeAttacksRight ? 'right' : 'left'}.
          </p>
        </section>
      </div>
      {q && (
        <div className="run-quality">
          <span>{q.frames} analyzed frames</span>
          <span>{Math.round(q.ballObservedFraction * 100)}% ball observed</span>
          <span>{Math.round(q.calibratedFraction * 100)}% pitch calibrated</span>
          <span>{q.jevResponses} Jev judgments</span>
          <span>{q.processingSeconds.toFixed(1)}s processing</span>
          <span>Coverage ≠ accuracy</span>
        </div>
      )}
    </section>
  );
}

export default memo(PipelineInsights);
