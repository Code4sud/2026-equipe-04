import { useEffect, useRef, useState } from 'react';
import type { Skill } from '../api/types';
import { TalentStarShape } from './Icons';

const HEIGHT = 72;
const MARGIN = 16;
const MAX_STOPS = 9;

function pointAt(progress: number, width: number) {
  const x = MARGIN + progress * (width - MARGIN * 2);
  const y = HEIGHT / 2 + Math.sin(progress * Math.PI * 2.6 + 0.5) * 16;
  return { x, y };
}

/** Le chemin suit l'ordre du récit : vert pour un talent gardé, étoile pour un talent à regarder. */
export function TalentRoute({ talents }: { talents: Skill[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(320);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const stops = talents
    .filter((talent) => talent.status !== 'rejected')
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .slice(-MAX_STOPS);
  const samples = Array.from({ length: 41 }, (_, index) => pointAt(index / 40, width));
  const path = samples
    .map(({ x, y }, index) => `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join('');

  return (
    <div className="route" ref={containerRef} aria-hidden="true">
      <svg viewBox={`0 0 ${width} ${HEIGHT}`}>
        <path
          d={path}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2.5"
          strokeDasharray="2 8"
          strokeLinecap="round"
        />
        {stops.map((talent, index) => {
          const { x, y } = pointAt((index + 1) / (stops.length + 1), width);
          return talent.status === 'validated' ? (
            <circle key={talent.id} cx={x} cy={y} r="7" fill="var(--color-positive-mark)" />
          ) : (
            <svg key={talent.id} x={x - 11} y={y - 11} width="22" height="22" viewBox="0 0 40 40">
              <TalentStarShape />
            </svg>
          );
        })}
      </svg>
    </div>
  );
}
