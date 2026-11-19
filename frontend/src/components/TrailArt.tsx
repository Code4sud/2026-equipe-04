import { TalentStarShape } from './Icons';

function Star({ x, y, size }: { x: number; y: number; size: number }) {
  return (
    <svg x={x} y={y} width={size} height={size} viewBox="0 0 40 40">
      <TalentStarShape />
    </svg>
  );
}

/** Le sentier de l'accueil : soleil, collines et talents posés le long de la route. */
export function TrailArt() {
  return (
    <svg className="trail-art" viewBox="0 0 260 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <circle cx="184" cy="62" r="44" fill="var(--color-talent)" opacity="0.4" />
      <circle cx="184" cy="62" r="29" fill="var(--color-talent)" opacity="0.75" />
      <path d="M0 126C44 102 86 112 132 124S222 130 260 106V220H0z" fill="var(--color-peach)" opacity="0.55" />
      <path d="M0 158C60 136 112 156 170 148S238 136 260 142V220H0z" fill="var(--color-accent-soft)" />
      <path
        d="M16 204C62 172 96 198 136 178S206 164 242 132"
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="2.5"
        strokeDasharray="2 8"
        strokeLinecap="round"
      />
      <Star x={34} y={170} size={24} />
      <Star x={214} y={122} size={26} />
    </svg>
  );
}
