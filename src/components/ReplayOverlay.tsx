import type { Frame } from '../core/model';
export default function ReplayOverlay({
  frame,
  width,
  height,
  selected,
  onSelect,
}: {
  frame: Frame;
  width: number;
  height: number;
  selected: number;
  onSelect: (id: number) => void;
}) {
  return (
    <svg
      className="video-overlay neural-overlay"
      viewBox={`0 0 ${width} ${height}`}
      aria-label="Neural player and ball detections"
    >
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
            strokeDasharray={frame.ball.status === 'predicted' ? '5 4' : undefined}
          />
          <text
            x={(frame.ball.image.x / 100) * width + 20}
            y={(frame.ball.image.y / 100) * height}
            fontSize="16"
            fill="#fff277"
          >
            {frame.ball.status === 'predicted' ? 'predicted' : 'ball'}
          </text>
        </g>
      )}
    </svg>
  );
}
