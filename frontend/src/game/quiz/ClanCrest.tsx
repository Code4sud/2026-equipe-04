const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 3.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

/** Symboles des clans, dessinés pour Flaire dans une boîte de 48 × 48. */
function Glyph({ icon }: { icon: string }) {
  switch (icon) {
    case 'hammer':
      return (
        <g transform="rotate(45 24 24)">
          <rect x="13" y="6" width="22" height="10" rx="2.5" {...stroke} />
          <path d="M24 16v27" {...stroke} />
        </g>
      );
    case 'compass':
      return (
        <>
          <circle cx="24" cy="24" r="18" {...stroke} />
          <path d="M24 10l5 14-5 14-5-14z" {...stroke} />
          <path d="M24 10l5 14H19z" fill="currentColor" />
        </>
      );
    case 'feather':
      return (
        <>
          <path d="M38 7C21 8 11 20 11 37c16 0 27-11 27-30z" {...stroke} />
          <path d="M11 37L30 18M11 37l-4 4" {...stroke} />
        </>
      );
    case 'hands':
      return (
        <>
          <path d="M5 25c0 10 8 16 19 16s19-6 19-16" {...stroke} />
          <path d="M5 25c5 0 9 2 11 6M43 25c-5 0-9 2-11 6" {...stroke} />
          <path d="M24 7l2.6 5.6 6.1.6-4.6 4.1 1.3 6-5.4-3.1-5.4 3.1 1.3-6-4.6-4.1 6.1-.6z" {...stroke} strokeWidth={2.6} />
        </>
      );
    case 'flag':
      return (
        <>
          <path d="M12 43V5" {...stroke} />
          <path d="M12 8c7-4 13 4 24 0v16c-11 4-17-4-24 0" {...stroke} />
        </>
      );
    case 'key':
      return (
        <>
          <circle cx="15" cy="24" r="8" {...stroke} />
          <path d="M23 24h19M35 24v7M41 24v5" {...stroke} />
        </>
      );
    default:
      return <path d="M24 6l5 11 12 1-9 8 3 12-11-6-11 6 3-12-9-8 12-1z" {...stroke} />;
  }
}

/** Blason original d'un clan : un écu arrondi et son symbole. */
export function ClanCrest({ icon, label }: { icon: string; label: string }) {
  return (
    <svg className="quiz-crest" viewBox="0 0 120 140" role="img" aria-label={label}>
      <path
        className="quiz-crest__shield"
        d="M60 6c16 8 34 10 50 8v48c0 36-22 58-50 72C32 120 10 98 10 62V14c16 2 34 0 50-8z"
      />
      <path
        className="quiz-crest__field"
        d="M60 18c13 7 27 9 39 8v36c0 29-17 47-39 59-22-12-39-30-39-59V26c12 1 26-1 39-8z"
      />
      <circle className="quiz-crest__dot" cx="48" cy="34" r="2.5" />
      <circle className="quiz-crest__dot" cx="60" cy="31" r="2.5" />
      <circle className="quiz-crest__dot" cx="72" cy="34" r="2.5" />
      <g className="quiz-crest__glyph" transform="translate(36 46)">
        <Glyph icon={icon} />
      </g>
    </svg>
  );
}
