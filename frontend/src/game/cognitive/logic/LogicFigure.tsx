import { useId } from 'react';
import { cogFr } from '../cognitive.fr';
import type { LogicCell, LogicLine, LogicShape } from '../settings';

const t = cogFr.logic;

/** Positions des formes dans une case de 100 × 100, selon leur nombre. */
const LAYOUTS: Record<number, [number, number][]> = {
  1: [[50, 50]],
  2: [
    [29, 50],
    [71, 50],
  ],
  3: [
    [50, 27],
    [27, 70],
    [73, 70],
  ],
  4: [
    [29, 29],
    [71, 29],
    [29, 71],
    [71, 71],
  ],
  5: [
    [26, 26],
    [74, 26],
    [50, 50],
    [26, 74],
    [74, 74],
  ],
  6: [
    [29, 22],
    [71, 22],
    [29, 50],
    [71, 50],
    [29, 78],
    [71, 78],
  ],
};
const RADIUS: Record<number, number> = { 1: 30, 2: 18, 3: 17, 4: 16, 5: 13, 6: 12 };
const LINES: Record<LogicLine, string> = {
  h: 'M14 50H86',
  v: 'M50 14V86',
  d1: 'M17 17L83 83',
  d2: 'M17 83L83 17',
};

function polygon(cx: number, cy: number, points: [number, number][]): string {
  return points.map(([x, y]) => `${(cx + x).toFixed(1)},${(cy + y).toFixed(1)}`).join(' ');
}

function star(r: number): [number, number][] {
  return Array.from({ length: 10 }, (_, index) => {
    const radius = index % 2 === 0 ? r : r * 0.45;
    const angle = (Math.PI / 5) * index - Math.PI / 2;
    return [radius * Math.cos(angle), radius * Math.sin(angle)];
  });
}

function hexagon(r: number): [number, number][] {
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 3) * index - Math.PI / 2;
    return [r * Math.cos(angle), r * Math.sin(angle)];
  });
}

function Shape({
  shape,
  cx,
  cy,
  r,
  rotate,
  paint,
}: {
  shape: LogicShape;
  cx: number;
  cy: number;
  r: number;
  rotate: number;
  paint: { fill: string; stroke: string; strokeWidth: number; strokeLinejoin: 'round' };
}) {
  switch (shape) {
    case 'circle':
      return <circle cx={cx} cy={cy} r={r * 0.92} {...paint} />;
    case 'square':
      return <rect x={cx - r * 0.8} y={cy - r * 0.8} width={r * 1.6} height={r * 1.6} rx={r * 0.12} {...paint} />;
    case 'triangle':
      return (
        <polygon
          points={polygon(cx, cy, [
            [0, -r],
            [r * 0.95, r * 0.72],
            [-r * 0.95, r * 0.72],
          ])}
          {...paint}
        />
      );
    case 'diamond':
      return (
        <polygon
          points={polygon(cx, cy, [
            [0, -r],
            [r * 0.78, 0],
            [0, r],
            [-r * 0.78, 0],
          ])}
          {...paint}
        />
      );
    case 'star':
      return <polygon points={polygon(cx, cy, star(r))} {...paint} />;
    case 'hexagon':
      return <polygon points={polygon(cx, cy, hexagon(r))} {...paint} />;
    case 'arrow':
      return (
        <polygon
          transform={`rotate(${rotate} ${cx} ${cy})`}
          points={polygon(cx, cy, [
            [0, -r],
            [r * 0.78, -r * 0.12],
            [r * 0.3, -r * 0.12],
            [r * 0.3, r],
            [-r * 0.3, r],
            [-r * 0.3, -r * 0.12],
            [-r * 0.78, -r * 0.12],
          ])}
          {...paint}
        />
      );
  }
}

/** Dessin d'une case de matrice, en currentColor : aucune information ne passe par la couleur. */
export function LogicFigure({ cell }: { cell: LogicCell }) {
  const pattern = `cog-stripes-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  if (cell.lines) {
    return (
      <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
        <rect x="10" y="10" width="80" height="80" rx="8" className="cog-figure__frame" />
        {cell.lines.map((line) => (
          <path key={line} d={LINES[line]} stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
        ))}
      </svg>
    );
  }
  const count = Math.min(Math.max(cell.count ?? 1, 1), 6);
  const fill = cell.fill ?? 'full';
  const paint = {
    fill: fill === 'full' ? 'currentColor' : fill === 'striped' ? `url(#${pattern})` : 'none',
    stroke: 'currentColor',
    strokeWidth: count > 4 ? 3.5 : 4.5,
    strokeLinejoin: 'round' as const,
  };
  return (
    <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      {fill === 'striped' && (
        <defs>
          <pattern id={pattern} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="3" height="7" fill="currentColor" />
          </pattern>
        </defs>
      )}
      {LAYOUTS[count].map(([cx, cy], index) => (
        <Shape
          key={index}
          shape={cell.shape ?? 'circle'}
          cx={cx}
          cy={cy}
          r={RADIUS[count]}
          rotate={cell.rotate ?? 0}
          paint={paint}
        />
      ))}
    </svg>
  );
}

/** La même case en mots, pour les lecteurs d'écran. */
export function describeCell(cell: LogicCell | null): string {
  if (!cell) return t.missing;
  if (cell.lines) return t.linesLabel(cell.lines.map((line) => t.lines[line] ?? line));
  const [one, many, gender] = t.shapes[cell.shape ?? 'circle'] ?? [cell.shape, cell.shape, 'm'];
  const count = cell.count ?? 1;
  const [masculine, feminine] = t.fills[cell.fill ?? 'full'] ?? ['', ''];
  const fill = (gender === 'f' ? feminine : masculine) + (count > 1 ? 's' : '');
  const direction = cell.shape === 'arrow' ? ` ${t.directions[(((cell.rotate ?? 0) % 360) + 360) % 360] ?? ''}` : '';
  return `${count} ${count > 1 ? many : one} ${fill}${direction}`.trim();
}
