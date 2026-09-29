import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Crosshair,
  Film,
  Layers3,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react';
import { createDemo } from './core/demo';
import { playerMetrics, stateAt, type Analysis } from './core/model';
import { analyzeVideo } from './core/analyze';
import Pitch from './components/Pitch';
import PipelineInsights from './components/PipelineInsights';
import ReplayOverlay from './components/ReplayOverlay';
import ActionOverlay from './components/ActionOverlay';
import { analyzeWithPipeline, getHealth, loadRealDemo, type Health } from './core/pipeline';
import { homography, enrichFrames, type BallMark, type Matrix } from './core/geometry';
import { detectEvents, frameAt, type Point } from './core/model';
const demo = createDemo();
const clock = (n: number) =>
  `${Math.floor(n / 60)
    .toString()
    .padStart(2, '0')}:${Math.floor(n % 60)
    .toString()
    .padStart(2, '0')}`;
export default function App() {
  const [analysis, setAnalysis] = useState<Analysis>(demo),
    [time, setTime] = useState(7),
    [playing, setPlaying] = useState(false),
    [rate, setRate] = useState(1),
    [selected, setSelected] = useState(9),
    [trails, setTrails] = useState(true),
    [shape, setShape] = useState(true),
    [heat, setHeat] = useState(false),
    [modal, setModal] = useState<'upload' | 'about' | null>(null),
    [progress, setProgress] = useState<number | null>(null),
    [error, setError] = useState(''),
    [videoUrl, setVideoUrl] = useState(''),
    [tab, setTab] = useState<'moments' | 'players'>('moments');
  const [health, setHealth] = useState<Health | null>(null),
    [uploadMode, setUploadMode] = useState<'pipeline' | 'browser'>('pipeline'),
    [jobStage, setJobStage] = useState('preparing'),
    [homeAttacksRight, setHomeAttacksRight] = useState(true);
  const [videoSize, setVideoSize] = useState({ w: 16, h: 9 });
  const [matrix, setMatrix] = useState<Matrix | null>(null),
    [marks, setMarks] = useState<BallMark[]>([]),
    [tool, setTool] = useState<'corners' | 'ball' | null>(null),
    [corners, setCorners] = useState<Point[]>([]);
  const input = useRef<HTMLInputElement>(null),
    video = useRef<HTMLVideoElement>(null),
    abort = useRef<AbortController | null>(null),
    workspace = useRef<HTMLDivElement>(null);
  const local = analysis.source === 'local',
    pipeline = analysis.source === 'pipeline',
    footage = local || pipeline;
  const calibrated = pipeline
    ? Boolean(frameAt(analysis.frames, time).calibration?.valid)
    : !local || matrix !== null;
  const activeAnalysis = useMemo(() => {
    if (!local) return analysis;
    const frames = enrichFrames(analysis.frames, matrix, marks);
    return { ...analysis, frames, events: matrix ? detectEvents(frames) : [] };
  }, [analysis, local, matrix, marks]);
  const state = useMemo(() => stateAt(activeAnalysis.frames, time), [activeAnalysis, time]);
  const metrics = useMemo(
    () => playerMetrics(activeAnalysis.frames, selected, time),
    [activeAnalysis, selected, time],
  );
  useEffect(
    () => () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    },
    [videoUrl],
  );
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    let mounted = true;
    void getHealth()
      .then(async (h) => {
        if (!mounted) return;
        setHealth(h);
        if (h.demoAvailable) {
          const real = await loadRealDemo();
          if (!mounted) return;
          setAnalysis({ ...real, name: 'Bundesliga · real match analysis' });
          setVideoUrl('/api/demo/video');
          setTime(1);
          setSelected(real.frames[0]?.players.find((p) => p.team === 'home')?.id ?? 1);
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);
  useEffect(() => {
    if (!playing || footage) return;
    let prev = performance.now();
    let id = 0;
    const tick = (now: number) => {
      const dt = (now - prev) / 1000;
      prev = now;
      setTime((t) => {
        const next = t + dt * rate;
        if (next >= analysis.duration) {
          setPlaying(false);
          return analysis.duration;
        }
        return next;
      });
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [playing, rate, footage, analysis.duration]);
  useEffect(() => {
    const element = video.current;
    if (!footage || !element) return;
    let callback = 0;
    let animation = 0;
    let stopped = false;
    const update = (t: number) => {
      setTime(Math.min(t, analysis.duration));
      if (t >= analysis.duration) {
        element.pause();
        setPlaying(false);
      }
    };
    // Decode/presentation clock preserves source cadence, including 60 FPS footage.
    if (typeof element.requestVideoFrameCallback === 'function') {
      const next = (_now: number, metadata: VideoFrameCallbackMetadata) => {
        if (stopped) return;
        update(metadata.mediaTime);
        callback = element.requestVideoFrameCallback(next);
      };
      callback = element.requestVideoFrameCallback(next);
    } else {
      const next = () => {
        if (stopped) return;
        if (!element.paused) update(element.currentTime);
        animation = requestAnimationFrame(next);
      };
      animation = requestAnimationFrame(next);
    }
    return () => {
      stopped = true;
      if (callback) element.cancelVideoFrameCallback(callback);
      cancelAnimationFrame(animation);
    };
  }, [footage, videoUrl, analysis.duration]);
  useEffect(() => {
    if (!video.current) return;
    video.current.playbackRate = rate;
    if (playing)
      void video.current.play().catch(() => {
        setPlaying(false);
        setError('Playback could not start. Try another video format.');
      });
    else video.current.pause();
  }, [playing, rate, videoUrl]);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement as HTMLElement;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    dialog?.querySelector<HTMLElement>('button')?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        abort.current?.abort();
        setModal(null);
      }
      if (e.key === 'Tab' && dialog) {
        const els = [
          ...dialog.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not([hidden]), select, a[href]',
          ),
        ];
        const first = els[0],
          last = els.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => {
      document.removeEventListener('keydown', handler);
      previous?.focus();
    };
  }, [modal]);
  const seek = useCallback((t: number) => {
    setTime(t);
    if (video.current) video.current.currentTime = t;
  }, []);
  const togglePlay = () => {
    setTool(null);
    if (time >= analysis.duration) seek(0);
    setPlaying((p) => !p);
  };
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      if (
        ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName) ||
        modal
      )
        return;
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });
  async function upload(file: File) {
    setError('');
    setPlaying(false);
    setProgress(0);
    const controller = new AbortController();
    abort.current = controller;
    try {
      const result =
        uploadMode === 'pipeline'
          ? await analyzeWithPipeline(
              file,
              (n, stage) => {
                setProgress(n);
                setJobStage(stage);
              },
              controller.signal,
              homeAttacksRight,
            )
          : await analyzeVideo(file, setProgress, controller.signal);
      setMatrix(null);
      setMarks([]);
      setTool(null);
      setCorners([]);
      setVideoUrl(result.videoUrl ?? URL.createObjectURL(file));
      setAnalysis(result);
      setTime(0);
      setSelected(result.frames[0]?.players[0]?.id ?? 1);
      setModal(null);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally {
      setProgress(null);
      abort.current = null;
      if (input.current) input.current.value = '';
    }
  }
  function exportData() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            {
              ...activeAnalysis,
              schemaVersion: pipeline ? 2 : 1,
              calibration: matrix,
              ballMarks: marks,
              coordinates: calibrated ? 'normalized-pitch' : 'normalized-image',
              judgment: pipeline ? 'jev-and-state-rules' : 'deterministic-heuristics',
            },
            null,
            2,
          ),
        ],
        { type: 'application/json' },
      ),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pitchstate-analysis.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function markPoint(e: React.MouseEvent<HTMLDivElement>) {
    if (!tool || !video.current) return;
    const r = e.currentTarget.getBoundingClientRect(),
      v = video.current,
      scale = Math.min(r.width / v.videoWidth, r.height / v.videoHeight),
      w = v.videoWidth * scale,
      h = v.videoHeight * scale;
    const point = {
      x: ((e.clientX - r.left - (r.width - w) / 2) / w) * 100,
      y: ((e.clientY - r.top - (r.height - h) / 2) / h) * 100,
    };
    if (point.x < 0 || point.x > 100 || point.y < 0 || point.y > 100) return;
    if (tool === 'corners') {
      const next = [...corners, point];
      setCorners(next);
      if (next.length === 4) {
        try {
          setMatrix(homography(next));
          setTool(null);
          setError('');
        } catch (err) {
          setError((err as Error).message);
          setCorners([]);
        }
      }
    } else {
      const stamp = Math.round(time * 5) / 5;
      setMarks((old) => [
        ...old.filter((m) => Math.abs(m.time - stamp) > 0.05),
        { ...point, time: stamp },
      ]);
      seek(Math.min(analysis.duration, stamp + 0.4));
    }
  }
  const props = {
    frames: activeAnalysis.frames,
    time,
    selected,
    onSelect: setSelected,
    trails,
    shape,
    heat,
    local: !calibrated,
  };
  return (
    <>
      <header className="header">
        <a className="brand" href="./">
          <span className="brand-icon">
            <Activity size={22} />
          </span>
          PitchState<span className="beta">LAB</span>
        </a>
        <nav>
          <span className="nav-active">Playground</span>
          <button onClick={() => setModal('about')}>
            How it works <ArrowRight size={14} />
          </button>
        </nav>
        <div className="header-right">
          <span className="privacy">
            <span className="status-dot" />{' '}
            {health?.ready ? 'Neural pipeline ready' : 'Inference companion offline'}
          </span>
          <a href="https://github.com/KennyMx/PitchState" target="_blank" rel="noreferrer">
            GitHub ↗
          </a>
        </div>
      </header>
      <main>
        <section className="intro">
          <div>
            <div className="eyebrow">THE SOCCER ANALYSIS PLAYGROUND</div>
            <h1>
              See the game beneath the game<span>.</span>
            </h1>
            <p>Every movement tells a story. Explore how a play unfolds.</p>
          </div>
          <button
            className="primary"
            onClick={() => {
              setError('');
              setModal('upload');
            }}
          >
            <Upload size={16} /> Upload a clip
          </button>
        </section>
        <div className="workspace" ref={workspace}>
          <div className="workspace-bar">
            <div className="clip-title">
              <span className="clip-icon">
                <Film size={18} />
              </span>
              <div>
                <strong>{analysis.name}</strong>
                <span>
                  {pipeline
                    ? 'Neural perception → game state → Jev forecasts'
                    : local
                      ? 'Your clip · experimental tracking'
                      : 'Example 01 · a transition through the left channel'}
                </span>
              </div>
            </div>
            <div className="workspace-meta">
              <span className="tag">
                {pipeline ? 'REAL FOOTAGE · JEV' : local ? 'LOCAL CLIP' : 'SIMULATED PLAY'}
              </span>
              <span>
                {clock(analysis.duration)} ·{' '}
                {analysis.video ? `${analysis.video.fps} FPS replay · ` : ''}
                {analysis.sampleFps ?? (footage ? 5 : 10)} Hz analysis
              </span>
              <button
                className="icon-button"
                aria-label="Export analysis JSON"
                onClick={exportData}
              >
                <ArrowDownToLine size={17} />
              </button>
            </div>
          </div>
          <div className="view-grid">
            <section className="main-view">
              <div className="view-top">
                <span>
                  <span className="status-dot" />
                  {footage ? 'ORIGINAL FOOTAGE' : 'TACTICAL REPLAY'}
                </span>
                <span>
                  {pipeline
                    ? 'Learned player + ball detection'
                    : local
                      ? 'On-device processing'
                      : 'Illustrative sequence · not match footage'}
                </span>
              </div>
              <div className={`stage ${tool ? 'marking' : ''}`} onClick={markPoint}>
                {footage ? (
                  <>
                    <video
                      ref={video}
                      src={videoUrl}
                      onLoadedMetadata={(e) => {
                        setVideoSize({
                          w: e.currentTarget.videoWidth,
                          h: e.currentTarget.videoHeight,
                        });
                        e.currentTarget.currentTime = time;
                      }}
                      playsInline
                      onSeeked={(e) =>
                        setTime(Math.min(e.currentTarget.currentTime, analysis.duration))
                      }
                      onEnded={() => {
                        setPlaying(false);
                        setTime(analysis.duration);
                      }}
                      onError={() => setError('The browser cannot play this video. Try H.264 MP4.')}
                    />
                    {pipeline && (
                      <ActionOverlay analysis={analysis} time={Math.floor(time * 5) / 5} />
                    )}
                    {pipeline ? (
                      <ReplayOverlay
                        frame={frameAt(analysis.frames, time)}
                        width={videoSize.w}
                        height={videoSize.h}
                        selected={selected}
                        onSelect={setSelected}
                      />
                    ) : (
                      <svg
                        className="video-overlay"
                        viewBox={`0 0 ${videoSize.w} ${videoSize.h}`}
                        aria-hidden="true"
                      >
                        {frameAt(analysis.frames, time).players.map((p) => (
                          <g key={p.id}>
                            <rect
                              x={((p.x - 1.2) / 100) * videoSize.w}
                              y={((p.y - 6) / 100) * videoSize.h}
                              width={0.024 * videoSize.w}
                              height={0.06 * videoSize.h}
                              rx="2"
                              fill="none"
                              stroke={p.team === 'home' ? '#ffc5b3' : '#a7c8ff'}
                              strokeWidth={videoSize.w / 500}
                            />
                            <text
                              x={(p.x / 100) * videoSize.w}
                              y={((p.y - 7) / 100) * videoSize.h}
                              fontSize={videoSize.w / 65}
                              fill="white"
                              textAnchor="middle"
                            >
                              {p.id}
                            </text>
                          </g>
                        ))}
                        {corners.map((p, i) => (
                          <g key={i}>
                            <circle
                              cx={(p.x / 100) * videoSize.w}
                              cy={(p.y / 100) * videoSize.h}
                              r={videoSize.w / 100}
                              fill="#c5ef86"
                            />
                            <text
                              x={(p.x / 100) * videoSize.w}
                              y={(p.y / 100) * videoSize.h + videoSize.w / 220}
                              fontSize={videoSize.w / 70}
                              textAnchor="middle"
                              fill="#142016"
                            >
                              {i + 1}
                            </text>
                          </g>
                        ))}
                        {marks
                          .filter((m) => Math.abs(m.time - time) < 0.5)
                          .map((m) => (
                            <circle
                              key={m.time}
                              cx={(m.x / 100) * videoSize.w}
                              cy={(m.y / 100) * videoSize.h}
                              r={videoSize.w / 120}
                              fill="none"
                              stroke="white"
                              strokeWidth={videoSize.w / 400}
                            />
                          ))}
                      </svg>
                    )}
                  </>
                ) : (
                  <>
                    <div className="stadium">
                      <div className="stadium-label">
                        PITCHSTATE <span>EXPERIMENTAL FOOTBALL INTELLIGENCE</span> PITCHSTATE
                      </div>
                      <Pitch {...props} perspective />
                    </div>
                    <div className="scoreboard">
                      <b>HOME</b>
                      <span>0 — 0</span>
                      <b>AWAY</b>
                      <em>{clock(time)}</em>
                    </div>
                    <div className="direction">
                      ATTACKING DIRECTION <ArrowRight size={20} />
                    </div>
                  </>
                )}
                <div className="stage-bottom">
                  <span className="small-tag">
                    <Crosshair size={13} />
                    {state.frame.players.length} player{' '}
                    {pipeline ? 'tracks' : local ? 'candidates' : 'positions'}
                  </span>
                  <button
                    className="icon-button"
                    aria-label="Fullscreen workspace"
                    onClick={() => {
                      if (document.fullscreenElement) void document.exitFullscreen();
                      else void workspace.current?.requestFullscreen?.().catch(() => {});
                    }}
                  >
                    <Maximize2 size={16} />
                  </button>
                </div>
              </div>
              <div className="view-caption">
                <span>
                  <span className="legend home" />
                  {pipeline ? 'Team A' : 'Home'} <span className="legend away" />
                  {pipeline ? 'Team B' : 'Away'} <span className="legend ball" />
                  Ball
                </span>
                <span>
                  {pipeline
                    ? 'IDs are tracks · yellow = observed ball'
                    : local
                      ? 'Red / blue kit baseline'
                      : 'Select a player to explore their movement'}{' '}
                  <Crosshair size={12} />
                </span>
              </div>
            </section>
            <section className="map-view">
              <div className="view-top">
                <span>
                  <Layers3 size={14} /> {!calibrated ? 'CAMERA-SPACE MAP' : 'PITCH RECONSTRUCTION'}
                </span>
                <span className="live-label">SYNCED</span>
              </div>
              <div className="map-wrap">
                <Pitch {...props} />
              </div>
              <div className="map-caption">
                <span>
                  {!calibrated
                    ? 'Uncalibrated · image coordinates'
                    : pipeline
                      ? 'Automatic camera-aware pitch projection'
                      : local
                        ? 'Calibrated · fixed camera only'
                        : 'Top-down · normalized pitch'}
                </span>
                <ArrowRight size={16} />
              </div>
            </section>
          </div>
          {local && (
            <div className="annotation-bar">
              <div>
                <button
                  className={tool === 'corners' ? 'annotation-active' : ''}
                  onClick={() => {
                    setPlaying(false);
                    setTool(tool === 'corners' ? null : 'corners');
                    setCorners([]);
                  }}
                >
                  <Crosshair size={13} />
                  {tool === 'corners'
                    ? `Corner ${corners.length + 1} of 4`
                    : matrix
                      ? 'Recalibrate pitch'
                      : 'Calibrate pitch'}
                </button>
                <button
                  className={tool === 'ball' ? 'annotation-active' : ''}
                  disabled={!matrix}
                  onClick={() => {
                    setPlaying(false);
                    setTool(tool === 'ball' ? null : 'ball');
                  }}
                >
                  <Crosshair size={13} />
                  {tool === 'ball' ? 'Finish ball marking' : 'Mark ball'}
                </button>
                {marks.length > 0 && (
                  <button onClick={() => setMarks([])}>Clear {marks.length} marks</button>
                )}
              </div>
              <span>
                {tool === 'corners'
                  ? 'Click full-pitch corners: top left → top right → bottom right → bottom left. Fixed camera only.'
                  : tool === 'ball'
                    ? 'Click the ball in the video. Advances 0.4s per mark; gaps over 2s stay unknown.'
                    : matrix
                      ? 'Assisted geometry · assumes a 105 × 68 m pitch. Ball marks are interpolated.'
                      : 'Full pitch visible? Calibrate to enable ball marking and tactical hypotheses.'}
              </span>
            </div>
          )}
          <div className="transport">
            <button
              className="play-button"
              onClick={togglePlay}
              aria-label={playing ? 'Pause' : 'Play'}
            >
              {playing ? (
                <Pause size={18} fill="currentColor" />
              ) : (
                <Play size={18} fill="currentColor" />
              )}
            </button>
            <button className="icon-button" aria-label="Restart" onClick={() => seek(0)}>
              <RotateCcw size={15} />
            </button>
            <span className="time">
              {clock(time)}
              <span> / {clock(analysis.duration)}</span>
            </span>
            <div className="scrubber">
              <input
                aria-label="Playback position"
                type="range"
                min="0"
                max={analysis.duration}
                step=".05"
                value={time}
                onChange={(e) => seek(+e.target.value)}
                style={{
                  background: `linear-gradient(to right, #c4ee83 ${(time / analysis.duration) * 100}%, #343e37 ${(time / analysis.duration) * 100}%)`,
                }}
              />
              <div className="timeline-dots">
                {activeAnalysis.events.map((e, i) => (
                  <button
                    key={i}
                    style={{ left: `${(e.time / analysis.duration) * 100}%` }}
                    onClick={() => seek(e.time)}
                    aria-label={`Seek to ${e.kind} at ${clock(e.time)}`}
                    title={e.kind}
                  />
                ))}
              </div>
            </div>
            <select
              aria-label="Playback speed"
              value={rate}
              onChange={(e) => setRate(+e.target.value)}
            >
              <option value=".5">0.5×</option>
              <option value="1">1×</option>
              <option value="1.5">1.5×</option>
              <option value="2">2×</option>
            </select>
          </div>
          <div className="layer-bar">
            <span className="layer-title">VIEW LAYERS</span>
            {[
              { name: 'Movement trails', value: trails, set: setTrails },
              { name: 'Team shape', value: shape, set: setShape },
              { name: 'Player heatmap', value: heat, set: setHeat },
            ].map((layer) => (
              <button
                key={layer.name}
                className={layer.value ? 'layer enabled' : 'layer'}
                aria-pressed={layer.value}
                onClick={() => layer.set(!layer.value)}
              >
                <span className="checkbox">{layer.value && <Check size={11} />}</span>
                {layer.name}
              </button>
            ))}
            <span className="keyboard">Space to play / pause</span>
          </div>
        </div>
        {pipeline && (
          <PipelineInsights analysis={analysis} time={Math.floor(time * 5) / 5} onSeek={seek} />
        )}
        <div className="insights-grid">
          <section className="card state-card">
            <div className="card-heading">
              <h2>
                <Activity size={16} /> Game state
              </h2>
              <span className="tiny">AT {clock(time)}</span>
            </div>
            <div className="phase">
              <span className="status-dot" />
              {state.phase}
              <span className="heuristic">HEURISTIC</span>
            </div>
            <p className="state-detail">
              {pipeline
                ? 'State from refined tracks, ball evidence, and automatic pitch calibration. See Jev’s separate judgment above.'
                : local
                  ? matrix
                    ? 'Assisted analysis uses your pitch corners and interpolated ball marks. Tracking and tactical signals still need visual review.'
                    : 'Player positions are image-space estimates. Calibrate the pitch and mark the ball to explore tactical hypotheses.'
                  : state.phase === 'Quick progression'
                    ? 'Home is moving the ball forward quickly. Watch the space opening behind the midfield line.'
                    : state.phase === 'Under pressure'
                      ? 'Opponents are closing the space around the ball. Watch the supporting passing options.'
                      : 'Watch the distances between players as the shape adapts to the ball.'}
            </p>
            <div className="state-stats">
              <div>
                <span>POSSESSION ESTIMATE</span>
                <strong>
                  {state.owner
                    ? state.owner.team === 'home'
                      ? pipeline
                        ? 'Team A'
                        : 'Home'
                      : pipeline
                        ? 'Team B'
                        : 'Away'
                    : 'Unknown'}{' '}
                  {state.owner && <i className={`legend ${state.owner.team}`} />}
                </strong>
              </div>
              <div>
                <span>{!calibrated ? 'IMAGE WIDTH' : 'TEAM WIDTH'}</span>
                <strong>
                  {state.width.toFixed(0)}
                  <small>{!calibrated ? '%' : '% pitch'}</small>
                </strong>
              </div>
              <div>
                <span>NEARBY OPPONENTS</span>
                <strong>
                  {state.owner ? state.pressure : '—'}
                  <small> within {pipeline ? '6 m' : '12 units'}</small>
                </strong>
              </div>
            </div>
            <div className="card-note">
              <ShieldCheck size={13} />{' '}
              {pipeline
                ? 'Observed estimates · review calibration and ball confidence'
                : local
                  ? 'Low-confidence observations · review visually'
                  : 'Rule-based signals · inspect the evidence below'}
            </div>
          </section>
          <section className="card moments-card">
            <div className="card-heading">
              <div className="tabs">
                <button
                  className={tab === 'moments' ? 'active' : ''}
                  onClick={() => setTab('moments')}
                >
                  Key moments <span>{activeAnalysis.events.length}</span>
                </button>
                <button
                  className={tab === 'players' ? 'active' : ''}
                  onClick={() => setTab('players')}
                >
                  Player focus
                </button>
              </div>
              <span className="tiny">
                {tab === 'moments' ? 'CLICK TO EXPLORE' : `PLAYER ${selected}`}
              </span>
            </div>
            {tab === 'moments' ? (
              <div className="moments">
                {activeAnalysis.events.length ? (
                  activeAnalysis.events.map((event, i) => (
                    <button
                      className={`moment ${event.time <= time ? 'revealed' : ''}`}
                      key={i}
                      onClick={() => seek(event.time + 0.6)}
                    >
                      <span className="moment-time">{clock(event.time)}</span>
                      <span className="event-line" />
                      <span className="moment-text">
                        <strong>{event.kind}</strong>
                        <small>{event.detail}</small>
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))
                ) : (
                  <div className="empty">
                    <Crosshair size={23} />
                    <div>
                      <strong>Positions first. Meaning next.</strong>
                      <p>
                        No tactical events are inferred without ball evidence. Explore detected
                        players in Player focus.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="player-focus">
                <div className="player-picker">
                  <label htmlFor="player">Tracked player</label>
                  <select
                    id="player"
                    value={selected}
                    onChange={(e) => setSelected(+e.target.value)}
                  >
                    {state.frame.players.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.team} · #{p.id}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="player-numbers">
                  <div>
                    <strong>
                      {!calibrated ||
                      (pipeline &&
                        state.frame.players.find((p) => p.id === selected)?.speedMps == null)
                        ? '—'
                        : metrics.speed.toFixed(1)}
                      <small>km/h</small>
                    </strong>
                    <span>Current speed</span>
                  </div>
                  <div>
                    <strong>
                      {!calibrated ? '—' : metrics.distance.toFixed(1)}
                      <small>m</small>
                    </strong>
                    <span>Distance covered</span>
                  </div>
                </div>
                <p>
                  {pipeline
                    ? 'Estimated from automatically calibrated track motion. Camera-fit errors and identity switches can distort measurements.'
                    : local
                      ? 'Measurements require a fixed, calibrated camera. Kit detections and ID changes can distort estimates.'
                      : 'Simulated measurements on a 105 × 68 m pitch. Select a marker on either view to follow that player.'}
                </p>
              </div>
            )}
          </section>
        </div>
        <footer>
          <span className="footer-brand">
            PitchState <span>A different perspective on the beautiful game.</span>
          </span>
          <button onClick={() => setModal('about')}>
            <CircleHelp size={14} /> About this experiment
          </button>
        </footer>
      </main>
      {error && !modal && (
        <div className="toast" role="alert">
          {error}
          <button onClick={() => setError('')} aria-label="Dismiss error">
            <X size={16} />
          </button>
        </div>
      )}
      {modal && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && progress === null) setModal(null);
          }}
        >
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <button
              className="modal-close icon-button"
              aria-label="Close dialog"
              onClick={() => {
                abort.current?.abort();
                setModal(null);
              }}
            >
              <X size={20} />
            </button>
            {modal === 'upload' ? (
              <>
                <div className="modal-symbol">
                  <Upload size={25} />
                </div>
                <div className="eyebrow">BRING YOUR OWN PLAY</div>
                <h2 id="modal-title">Your clip. A new perspective.</h2>
                <p>
                  Soccer-trained models track players and the ball, reconstruct pitch geometry,
                  maintain game state, and ask Jev what may happen next. Wide-angle match footage
                  works best.
                </p>
                <div className="upload-options">
                  <label>
                    Analysis engine
                    <select
                      value={uploadMode}
                      onChange={(e) => setUploadMode(e.target.value as 'pipeline' | 'browser')}
                      disabled={progress !== null}
                    >
                      <option value="pipeline">Neural pipeline + Jev</option>
                      <option value="browser">Legacy browser kit-color baseline</option>
                    </select>
                  </label>
                  {uploadMode === 'pipeline' && (
                    <>
                      <label>
                        Team A attack direction
                        <select
                          value={String(homeAttacksRight)}
                          onChange={(e) => setHomeAttacksRight(e.target.value === 'true')}
                          disabled={progress !== null}
                        >
                          <option value="true">Toward the right goal →</option>
                          <option value="false">Toward the left goal ←</option>
                        </select>
                      </label>
                      <p>
                        {health?.ready
                          ? 'Local inference worker connected. CPU analysis can take several minutes.'
                          : 'Start the inference companion with npm run server. No synthetic results are substituted when it is offline.'}
                      </p>
                    </>
                  )}
                </div>
                <div
                  className="dropzone"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (progress === null && e.dataTransfer.files[0])
                      void upload(e.dataTransfer.files[0]);
                  }}
                >
                  <Film size={30} />
                  <strong>
                    {progress === null
                      ? 'Drop a soccer clip here'
                      : `Analyzing… ${progress}% · ${jobStage}`}
                  </strong>
                  {progress === null ? (
                    <>
                      <span>MP4 or WebM · up to 60 seconds · 100 MB max</span>
                      <button className="primary" onClick={() => input.current?.click()}>
                        Choose video <ArrowRight size={16} />
                      </button>
                    </>
                  ) : (
                    <>
                      <progress value={progress} max="100" />
                      <button onClick={() => abort.current?.abort()}>Cancel analysis</button>
                    </>
                  )}
                  <input
                    ref={input}
                    type="file"
                    accept="video/mp4,video/webm,video/quicktime"
                    hidden
                    onChange={(e) => {
                      if (e.target.files?.[0]) void upload(e.target.files[0]);
                    }}
                  />
                </div>
                {progress !== null && uploadMode === 'pipeline' && (
                  <p>
                    We analyze the complete clip, refine tracks and compute every judgment before
                    opening replay.
                  </p>
                )}
                {error && (
                  <p className="error" role="alert">
                    {error}
                  </p>
                )}
                <div className="upload-note">
                  <ShieldCheck size={17} />
                  <span>
                    {uploadMode === 'pipeline'
                      ? 'Video is processed by your local inference companion. Compact game-state features are sent to TypeSafe for Jev judgments; raw video is not sent to Jev, and the API key stays on the server. Jobs older than 24 hours are removed on startup or the next upload.'
                      : 'The legacy baseline stays in this browser and detects red/blue kit colors only.'}
                  </span>
                </div>
                <button
                  className="demo-link"
                  disabled={progress !== null}
                  onClick={() => {
                    setAnalysis(demo);
                    setMatrix(null);
                    setMarks([]);
                    setTool(null);
                    setVideoUrl('');
                    setTime(7);
                    setSelected(9);
                    setModal(null);
                  }}
                >
                  Explore the simulated example <ArrowRight size={15} />
                </button>
              </>
            ) : (
              <>
                <div className="eyebrow">BUILT TO EXPLORE</div>
                <h2 id="modal-title">A changing game. A changing state.</h2>
                <p>PitchState turns timestamped observations into a replayable view of the game.</p>
                <div className="about-step">
                  <b>01</b>
                  <div>
                    <h3>Observe the movement</h3>
                    <p>
                      Soccer-specific neural models detect players, goalkeepers, referees, the ball,
                      and 32 pitch landmarks. Motion and appearance maintain tracks across frames.
                    </p>
                  </div>
                </div>
                <div className="about-step">
                  <b>02</b>
                  <div>
                    <h3>Maintain the state</h3>
                    <p>
                      Positions, movement history and team geometry update with the playhead.
                      Learned pitch landmarks calibrate neural uploads; uncertain geometry falls
                      back to camera coordinates.
                    </p>
                  </div>
                </div>
                <div className="about-step">
                  <b>03</b>
                  <div>
                    <h3>Make the evidence visible</h3>
                    <p>
                      Jev evaluates compact state windows and returns tactical phase and next-action
                      probability distributions. Missing evidence, predicted ball positions, and
                      stale judgments remain explicit.
                    </p>
                  </div>
                </div>
                <button className="primary" onClick={() => setModal(null)}>
                  Explore the playground <ArrowRight size={16} />
                </button>
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}
