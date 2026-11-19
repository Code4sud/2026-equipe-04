/**
 * Dessins de la fiche : emblèmes des clans, attributs, badges et petits ornements.
 * Tout est décrit en chemins SVG sur une grille de 24, pour servir aussi au dessin sur canvas.
 */

export interface GlyphPath {
  d: string;
  /** Rempli au lieu d'être tracé. */
  fill?: boolean;
}

const circle = (cx: number, cy: number, r: number) =>
  `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0z`;

/** Étoile à cinq branches centrée en (cx, cy). */
export function starPath(cx: number, cy: number, outer: number, inner = outer * 0.48) {
  const points = Array.from({ length: 10 }, (_, index) => {
    const radius = index % 2 ? inner : outer;
    const angle = -Math.PI / 2 + (index * Math.PI) / 5;
    return `${(cx + radius * Math.cos(angle)).toFixed(2)} ${(cy + radius * Math.sin(angle)).toFixed(2)}`;
  });
  return `M${points.join('L')}z`;
}

export const GLYPHS: Record<string, GlyphPath[]> = {
  // Clans et attributs
  hammer: [
    { d: 'M5.5 4h13A1.5 1.5 0 0 1 20 5.5V8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 8V5.5A1.5 1.5 0 0 1 5.5 4z' },
    { d: 'M8.5 4v5.5' },
    { d: 'M10.75 9.5h2.5v9.75a1.25 1.25 0 0 1-2.5 0z' },
  ],
  compass: [
    { d: circle(12, 12, 8.5) },
    { d: 'M12 5.6l2.3 6.4H9.7z', fill: true },
    { d: 'M9.7 12h4.6L12 18.4z' },
  ],
  feather: [
    { d: 'M20 4c-6.8.3-11.2 4.6-12.2 12.1C15.2 15.4 19.6 11 20 4z' },
    { d: 'M4 20l9.6-9.6' },
    { d: 'M10.3 13.7h3.4' },
  ],
  hands: [
    { d: 'M3 12.5c.8 4.4 4.3 7 9 7s8.2-2.6 9-7' },
    { d: 'M3 12.5h3.4c1 0 1.9.6 2.3 1.5M21 12.5h-3.4c-1 0-1.9.6-2.3 1.5' },
    { d: 'M12 19.5v-3M12 15V8.6' },
    { d: 'M12 10.6c0-2.5-1.8-4.1-4.3-4.1 0 2.5 1.8 4.1 4.3 4.1zM12 9c0-2.3 1.7-4 4.2-4 0 2.4-1.8 4-4.2 4z' },
  ],
  flag: [{ d: 'M6 21V3.5M4 21h4' }, { d: 'M6 4.5h12l-3 4 3 4H6' }],
  key: [
    { d: circle(7.5, 12, 3.5) },
    { d: circle(7.5, 12, 1) },
    { d: 'M11 12h9.5M17.5 12v3M20.5 12v2.2' },
  ],
  flame: [
    {
      d: 'M12 21c-3.7 0-6.3-2.6-6.3-6.1 0-3.9 3.2-5.7 3.8-9.9 1.7 1.3 2.6 3 2.7 5 1.2-.9 1.9-2.4 2-4.2 2.6 2.2 4.1 5.6 4.1 9.1 0 3.5-2.6 6.1-6.3 6.1z',
    },
    { d: 'M12 18.6c-1.3 0-2.3-.9-2.3-2.3 0-1.5 1.1-2.3 2.3-3.8 1.2 1.5 2.3 2.3 2.3 3.8 0 1.4-1 2.3-2.3 2.3z', fill: true },
  ],
  // Badges
  paw: [
    {
      d: 'M12 12.6c-2.9 0-5.2 2.7-5.2 4.9 0 1.5 1.1 2.3 2.5 2.3 1.1 0 1.7-.6 2.7-.6s1.6.6 2.7.6c1.4 0 2.5-.8 2.5-2.3 0-2.2-2.3-4.9-5.2-4.9z',
      fill: true,
    },
    { d: `${circle(6.4, 10.6, 1.7)}${circle(9.5, 6.9, 1.8)}${circle(14.5, 6.9, 1.8)}${circle(17.6, 10.6, 1.7)}`, fill: true },
  ],
  dice: [
    { d: 'M7 4h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z' },
    {
      d: `${circle(8.6, 8.6, 1.25)}${circle(15.4, 8.6, 1.25)}${circle(12, 12, 1.25)}${circle(8.6, 15.4, 1.25)}${circle(15.4, 15.4, 1.25)}`,
      fill: true,
    },
  ],
  map: [
    { d: 'M3 6.5l5.5-2 7 2 5.5-2v13l-5.5 2-7-2-5.5 2z' },
    { d: 'M8.5 4.5v13M15.5 6.5v13' },
    { d: 'M17.2 10.2l2 2M19.2 10.2l-2 2' },
  ],
  star: [{ d: starPath(12, 12.6, 8.6) }],
  stars: [{ d: starPath(10, 13.6, 6.8) }, { d: starPath(18.4, 6.2, 3.2) }, { d: starPath(19, 16.8, 2.6) }],
  hourglass: [
    { d: 'M6.5 3.5h11M6.5 20.5h11' },
    { d: 'M7.6 3.5c0 4.6 4.4 5.6 4.4 8.5s-4.4 3.9-4.4 8.5M16.4 3.5c0 4.6-4.4 5.6-4.4 8.5s4.4 3.9 4.4 8.5' },
    { d: 'M9.3 19.2c.6-1.8 1.6-2.6 2.7-3.2 1.1.6 2.1 1.4 2.7 3.2z', fill: true },
  ],
  chest: [
    { d: 'M4 11V9.5A4.5 4.5 0 0 1 8.5 5h7A4.5 4.5 0 0 1 20 9.5V11' },
    { d: 'M4 11h16v7.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z' },
    { d: 'M10.5 9.8h3v3.6h-3z', fill: true },
  ],
  sail: [
    { d: 'M3 16.5h18l-2.6 3.5H5.6z' },
    { d: 'M12 3v13.5' },
    { d: 'M12.8 4c3.4 2.6 5.7 6.6 5.7 10.5h-5.7zM11.2 6.5c-2.2 2.3-3.7 5-4.2 8h4.2z' },
  ],
  rune: [{ d: 'M12 3l7 9-7 9-7-9z' }, { d: 'M12 8.5l2.7 3.5-2.7 3.5-2.7-3.5z', fill: true }],
};

/** Icônes d'action de la fiche. */
export const ACTIONS: Record<string, GlyphPath[]> = {
  pencil: [{ d: 'M4 20l1-4.2L15.6 5.2a2 2 0 0 1 2.8 0l.4.4a2 2 0 0 1 0 2.8L8.2 19z' }, { d: 'M14 6.8l3.2 3.2' }],
  hide: [
    { d: 'M3.5 3.5l17 17' },
    { d: 'M10.4 5.2A9.4 9.4 0 0 1 12 5c5 0 8.5 4.5 9.5 7a13.6 13.6 0 0 1-2.7 3.8M6.6 6.6C4.6 8 3.2 9.9 2.5 12c1 2.5 4.5 7 9.5 7 1.8 0 3.4-.6 4.8-1.4' },
    { d: 'M9.9 9.9a3 3 0 0 0 4.2 4.2' },
  ],
  show: [
    { d: 'M2.5 12c1-2.5 4.5-7 9.5-7s8.5 4.5 9.5 7c-1 2.5-4.5 7-9.5 7s-8.5-4.5-9.5-7z' },
    { d: circle(12, 12, 3) },
  ],
  check: [{ d: 'M5 12.5l4.5 4.5L19 7.5' }],
  cross: [{ d: 'M6.5 6.5l11 11M17.5 6.5l-11 11' }],
  arrow: [{ d: 'M5 12h14M13 6l6 6-6 6' }],
  download: [{ d: 'M12 4v11M7 10.5l5 5 5-5M5 20h14' }],
};

export function glyphFor(name: string | null | undefined): GlyphPath[] {
  return (name && GLYPHS[name]) || GLYPHS.rune;
}

/** Les chemins d'un dessin, à placer dans un <svg> de 24 sur 24. */
export function GlyphShapes({ paths, strokeWidth = 1.8 }: { paths: GlyphPath[]; strokeWidth?: number }) {
  return (
    <>
      {paths.map((path, index) =>
        path.fill ? (
          <path key={index} d={path.d} fill="currentColor" />
        ) : (
          <path
            key={index}
            d={path.d}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ),
      )}
    </>
  );
}

export function Glyph({ name, className }: { name: string | null | undefined; className?: string }) {
  return (
    <svg className={className ?? 'sheet-glyph'} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <GlyphShapes paths={glyphFor(name)} />
    </svg>
  );
}

export function ActionIcon({ name }: { name: keyof typeof ACTIONS }) {
  return (
    <svg className="sheet-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <GlyphShapes paths={ACTIONS[name]} strokeWidth={2} />
    </svg>
  );
}

/** Écu du clan : bouclier à double filet et emblème au centre. */
export const CREST_SHIELD = 'M32 3l26 8v21c0 18-11 30-26 37C17 62 6 50 6 32V11z';
export const CREST_INNER = 'M32 9.3l20.2 6.2V32c0 14.2-8.4 24-20.2 30C20.2 56 11.8 46.2 11.8 32V15.5z';

export function Crest({ icon }: { icon: string | null }) {
  return (
    <svg className="sheet-crest" viewBox="0 0 64 72" aria-hidden="true" focusable="false">
      <path className="sheet-crest__shield" d={CREST_SHIELD} />
      <path className="sheet-crest__inner" d={CREST_INNER} />
      {icon ? (
        <g className="sheet-crest__emblem" transform="translate(17.6 19.6) scale(1.2)">
          <GlyphShapes paths={glyphFor(icon)} strokeWidth={1.7} />
        </g>
      ) : (
        <text className="sheet-crest__unknown" x="32" y="45" textAnchor="middle">
          ?
        </text>
      )}
    </svg>
  );
}

/** Sceau festonné des attributs et des badges, dessiné dans un carré de 80. */
export function sealPath(bumps = 14, radius = 36, depth = 3.2) {
  const step = (Math.PI * 2) / bumps;
  const points = Array.from({ length: bumps }, (_, index) => {
    const angle = -Math.PI / 2 + index * step;
    return [40 + radius * Math.cos(angle), 40 + radius * Math.sin(angle)];
  });
  const chord = 2 * radius * Math.sin(step / 2);
  // Rayon de l'arc qui relie deux points distants de `chord` avec une flèche `depth`.
  const bump = (chord * chord) / (8 * depth) + depth / 2;
  const [first] = points;
  const arcs = points
    .slice(1)
    .concat([first])
    .map(([x, y]) => `A${bump.toFixed(2)} ${bump.toFixed(2)} 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`)
    .join('');
  return `M${first[0].toFixed(2)} ${first[1].toFixed(2)}${arcs}z`;
}

const SEAL = sealPath();

export function Seal({ className }: { className?: string }) {
  return (
    <svg className={className ?? 'sheet-seal'} viewBox="0 0 80 80" aria-hidden="true" focusable="false">
      <path className="sheet-seal__edge" d={SEAL} />
      <circle className="sheet-seal__ring" cx="40" cy="40" r="28" />
    </svg>
  );
}

/** Fleuron des titres de section. */
export function Fleuron() {
  return (
    <svg className="sheet-fleuron" viewBox="0 0 28 12" aria-hidden="true" focusable="false">
      <path d="M14 1.5l4.5 4.5-4.5 4.5L9.5 6z" fill="currentColor" />
      <path
        d="M8 6C5.8 6 5 3.4 3 3.4 1.8 3.4 1.2 4.3 1.2 5.1M20 6c2.2 0 3 2.6 5 2.6 1.2 0 1.8-.9 1.8-1.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Ornement d'angle de la feuille, tourné par la CSS pour chaque coin. */
export function Corner({ className }: { className: string }) {
  return (
    <svg className={`sheet-corner ${className}`} viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <path
        d="M4 30V10a6 6 0 0 1 6-6h20M9 22v-8a5 5 0 0 1 5-5h8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M4 36.5l2.5-2.5L4 31.5 1.5 34zM36.5 4L34 6.5 31.5 4 34 1.5z" fill="currentColor" />
      <circle cx="14" cy="14" r="2" fill="currentColor" />
    </svg>
  );
}
