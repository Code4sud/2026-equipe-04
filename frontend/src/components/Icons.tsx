/** Dessin de l'étoile, réutilisable à l'intérieur d'une autre illustration. */
export function TalentStarShape() {
  return (
    <>
      <circle cx="20" cy="20" r="18" fill="var(--color-talent)" />
      <circle cx="20" cy="20" r="18" fill="none" stroke="var(--color-accent)" strokeWidth="2.5" />
      <path
        d="M20 9.5l3.1 6.4 7 1-5.1 4.9 1.2 7-6.2-3.3-6.2 3.3 1.2-7-5.1-4.9 7-1z"
        fill="var(--color-talent-star)"
        stroke="var(--color-accent)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </>
  );
}

export function TalentStar() {
  return (
    <svg className="talent-star" viewBox="0 0 40 40" aria-hidden="true">
      <TalentStarShape />
    </svg>
  );
}

const outline = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

export function ChatIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M3 4h14v9H9l-4 3v-3H3z" {...outline} />
    </svg>
  );
}

export function MapIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M2 5l5-2 6 2 5-2v12l-5 2-6-2-5 2zM7 3v12M13 5v12" {...outline} />
    </svg>
  );
}

export function PersonIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="7" r="3.5" {...outline} />
      <path d="M3 18c1-4 4-5 7-5s6 1 7 5" {...outline} />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M10 16V4M4.5 9.5L10 4l5.5 5.5" {...outline} strokeWidth={2.2} />
    </svg>
  );
}

export function MoonIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M16.5 12.2A7 7 0 0 1 7.8 3.5a7 7 0 1 0 8.7 8.7z" {...outline} />
    </svg>
  );
}

export function SunIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="3.4" {...outline} />
      <path
        d="M10 2.2v1.9M10 15.9v1.9M2.2 10h1.9M15.9 10h1.9M4.5 4.5l1.3 1.3M14.2 14.2l1.3 1.3M15.5 4.5l-1.3 1.3M5.8 14.2l-1.3 1.3"
        {...outline}
      />
    </svg>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8.5l3 3 7-7" {...outline} strokeWidth={2.6} />
    </svg>
  );
}

export function CrossIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M4 4l8 8M12 4l-8 8" {...outline} strokeWidth={2.4} />
    </svg>
  );
}

export function PinIcon() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <path d="M6 1C3.5 1 2 2.8 2 4.8 2 7.5 6 11 6 11s4-3.5 4-6.2C10 2.8 8.5 1 6 1z" fill="currentColor" />
    </svg>
  );
}
