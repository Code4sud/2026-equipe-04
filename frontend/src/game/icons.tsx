const outline = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

export function GamesIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <rect x="3" y="3" width="14" height="14" rx="3.5" {...outline} />
      <circle cx="7.2" cy="7.2" r="1" fill="currentColor" />
      <circle cx="12.8" cy="12.8" r="1" fill="currentColor" />
      <circle cx="10" cy="10" r="1" fill="currentColor" />
    </svg>
  );
}

export function SheetIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5 3h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4" {...outline} />
      <path d="M7.5 7.5h5.5M7.5 10.5h5.5M7.5 13.5h3" {...outline} />
    </svg>
  );
}
