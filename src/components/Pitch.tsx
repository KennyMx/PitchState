import { convexHull } from '../core/geometry';
import { frameAt, type Frame } from '../core/model';
interface Props {
  frames: Frame[];
  time: number;
  selected: number;
  onSelect: (id: number) => void;
  trails: boolean;
  shape: boolean;
  heat: boolean;
  perspective?: boolean;
  local?: boolean;
}
export default function Pitch({
  frames,
  time,
  selected,
  onSelect,
  trails,
  shape,
  heat,
  perspective = false,
  local = false,
}: Props) {
  const frame = frameAt(frames, time),
    home = frame.players.filter((p) => p.team === 'home');
  const trailFrames = frames.filter((f) => f.time <= time && f.time > time - 3);
  return (
    <svg
      className={`pitch ${perspective ? 'perspective' : ''}`}
      viewBox="-5 -6 110 112"
      preserveAspectRatio="none"
      role="group"
      aria-label={
        local ? 'Camera-space player reconstruction' : 'Interactive top-down pitch reconstruction'
      }
    >
      <defs>
        <pattern
          id={perspective ? 'stripes-main' : 'stripes-map'}
          width="20"
          height="100"
          patternUnits="userSpaceOnUse"
        >
          <rect width="10" height="100" fill="#ffffff" opacity=".025" />
        </pattern>
        <radialGradient id={perspective ? 'hot-main' : 'hot-map'}>
          <stop stopColor="#c8ed72" stopOpacity=".42" />
          <stop offset="1" stopColor="#c8ed72" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect
        x="0"
        y="0"
        width="100"
        height="100"
        rx=".6"
        fill={perspective ? '#305c43' : '#182d25'}
      />
      <rect
        width="100"
        height="100"
        fill={`url(#${perspective ? 'stripes-main' : 'stripes-map'})`}
      />
      <g fill="none" stroke="#d7e8d3" strokeOpacity=".32" strokeWidth=".35">
        <rect width="100" height="100" />
        <path d="M50 0v100M0 20h16v60H0M100 20H84v60h16M0 37h5v26H0M100 37h-5v26h5" />
        <ellipse cx="50" cy="50" rx="9" ry="14" />
        <ellipse cx="11" cy="50" rx=".4" ry=".6" />
        <ellipse cx="89" cy="50" rx=".4" ry=".6" />
        <path d="M16 39q8 11 0 22M84 39q-8 11 0 22M0 44h-2v12h2M100 44h2v12h-2" />
      </g>
      {heat &&
        frames
          .filter((f, i) => i % 5 === 0 && f.time <= time)
          .flatMap((f) =>
            f.players
              .filter((p) => p.id === selected)
              .map((p) => (
                <ellipse
                  key={f.time}
                  cx={p.x}
                  cy={p.y}
                  rx="7"
                  ry="10"
                  fill={`url(#${perspective ? 'hot-main' : 'hot-map'})`}
                />
              )),
          )}
      {shape && home.length > 2 && (
        <polygon
          points={convexHull(home)
            .map((p) => `${p.x},${p.y}`)
            .join(' ')}
          fill="#c8ed72"
          fillOpacity=".06"
          stroke="#c8ed72"
          strokeOpacity=".28"
          strokeWidth=".4"
          strokeDasharray="1 1"
        />
      )}
      {trails &&
        frame.players.map((p) => (
          <polyline
            key={p.id}
            points={trailFrames
              .map((f) => f.players.find((q) => q.id === p.id))
              .filter(Boolean)
              .map((q) => `${q!.x},${q!.y}`)
              .join(' ')}
            fill="none"
            stroke={p.team === 'home' ? '#d3f991' : '#9bafff'}
            strokeWidth={p.id === selected ? '.7' : '.3'}
            opacity={p.id === selected ? '.9' : '.35'}
          />
        ))}
      {frame.players.map((p) => (
        <g
          key={p.id}
          className="player"
          role="button"
          tabIndex={0}
          aria-label={`Select ${p.team} player ${p.id}`}
          onClick={() => onSelect(p.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onSelect(p.id);
            }
          }}
        >
          {p.id === selected && (
            <ellipse
              cx={p.x}
              cy={p.y}
              rx="3"
              ry="4.5"
              fill="none"
              stroke="#e1ffa9"
              strokeWidth=".35"
            />
          )}
          <ellipse cx={p.x + 0.3} cy={p.y + 1} rx="1.8" ry="2.5" fill="#000" opacity=".3" />
          <ellipse
            cx={p.x}
            cy={p.y}
            rx="1.6"
            ry="2.5"
            fill={p.team === 'home' ? '#c8ee85' : '#91a5ef'}
            stroke={p.team === 'home' ? '#e7ffc1' : '#c3cfff'}
            strokeWidth=".25"
          />
          <text
            x={p.x}
            y={p.y + 0.85}
            textAnchor="middle"
            fontSize="2.3"
            fill="#142019"
            fontWeight="700"
          >
            {p.id}
          </text>
        </g>
      ))}
      {frame.ball && (
        <g>
          <ellipse
            cx={frame.ball.x}
            cy={frame.ball.y}
            rx="1"
            ry="1.5"
            fill="white"
            stroke="#17241d"
            strokeWidth=".4"
          />
          <ellipse
            cx={frame.ball.x}
            cy={frame.ball.y}
            rx="2"
            ry="3"
            fill="none"
            stroke="white"
            strokeOpacity=".3"
            strokeWidth=".3"
          />
        </g>
      )}
    </svg>
  );
}
