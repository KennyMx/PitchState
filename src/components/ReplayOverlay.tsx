import type { Candidate } from '../core/pipeline';
import type { Frame } from '../core/model';
export default function ReplayOverlay({
  frame,
  width,
  height,
  selected,
  onSelect,
  forecast,
}: {
  frame: Frame;
  width: number;
  height: number;
  selected: number;
  onSelect: (id: number) => void;
  forecast?: Candidate;
}) {
  const target = frame.players.find((p) => p.id === forecast?.targetId)?.image;
  const origin = frame.players.find((p) => p.id === forecast?.actorId)?.image ?? frame.ball?.image;
  return (
    <svg
      className="video-overlay neural-overlay"
      viewBox={`0 0 ${width} ${height}`}
      aria-label="Neural player and ball detections"
    >
      <defs>
        <marker
          id="forecast-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10z" fill="#d0ff8e" />
        </marker>
      </defs>
      {forecast && target && origin && (
        <g className="forecast-route">
          <title>Predicted option: {forecast.label}</title>
          <line
            x1={(origin.x / 100) * width}
            y1={(origin.y / 100) * height}
            x2={(target.x / 100) * width}
            y2={(target.y / 100) * height}
            stroke="#102017"
            strokeWidth="7"
            opacity=".5"
          />
          <line
            x1={(origin.x / 100) * width}
            y1={(origin.y / 100) * height}
            x2={(target.x / 100) * width}
            y2={(target.y / 100) * height}
            stroke="#d0ff8e"
            strokeWidth="3"
            strokeDasharray="10 7"
            markerEnd="url(#forecast-arrow)"
            opacity=".9"
          />
          <circle
            cx={(target.x / 100) * width}
            cy={(target.y / 100) * height}
            r="20"
            fill="none"
            stroke="#d0ff8e"
            strokeWidth="3"
          />
        </g>
      )}
      {frame.players.map((p) => {
        const b = p.box;
        if (!b) return null;
        const color = p.team === 'home' ? '#d0ff8e' : p.team === 'away' ? '#a6baff' : '#e1e1d3';
        return (
          <g key={p.id} className="detection" onClick={() => onSelect(p.id)}>
            <rect
              x={b[0]}
              y={b[1]}
              width={b[2] - b[0]}
              height={b[3] - b[1]}
              rx="3"
              fill={selected === p.id ? '#c5ef8625' : 'transparent'}
              stroke={color}
              strokeWidth={selected === p.id ? 4 : 2}
              opacity=".85"
            />
            <rect x={b[0]} y={b[1] - 24} width="42" height="22" fill={color} rx="3" />
            <text
              x={b[0] + 21}
              y={b[1] - 8}
              textAnchor="middle"
              fontSize="17"
              fontWeight="700"
              fill="#142016"
            >
              {p.id}
            </text>
          </g>
        );
      })}
      {frame.ball?.image && (
        <g>
          <circle
            cx={(frame.ball.image.x / 100) * width}
            cy={(frame.ball.image.y / 100) * height}
            r="15"
            fill="none"
            stroke={frame.ball.status === 'observed' ? '#fff277' : '#ffb96b'}
            strokeWidth="3"
            strokeDasharray={frame.ball.status !== 'observed' ? '5 4' : undefined}
          />
          <text
            x={(frame.ball.image.x / 100) * width + 20}
            y={(frame.ball.image.y / 100) * height}
            fontSize="16"
            fill="#fff277"
          >
            {frame.ball.status === 'observed' ? 'ball' : frame.ball.status}
          </text>
        </g>
      )}
    </svg>
  );
}
