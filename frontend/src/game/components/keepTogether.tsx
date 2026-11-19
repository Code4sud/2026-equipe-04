import type { ReactNode } from 'react';

/** Mots à trait d'union qui ne se coupent pas en fin de ligne. */
const KEPT = /(mini-jeux)/i;

/**
 * Garde « mini-jeux » sur une seule ligne, sinon le navigateur peut couper au trait d'union
 * (« mini- » en fin de ligne, « jeux » au début de la suivante). Figtree n'a pas de trait d'union
 * insécable (U+2011) : une autre police le dessinerait, alors le mot passe dans un span sans retour
 * à la ligne. Pour un paragraphe : dans un conteneur flex, chaque morceau deviendrait un élément.
 */
export function keepTogether(text: string): ReactNode {
  const parts = text.split(KEPT);
  if (parts.length === 1) return text;
  return parts.map((part, index) =>
    index % 2 === 1 ? (
      <span key={index} style={{ whiteSpace: 'nowrap' }}>
        {part}
      </span>
    ) : (
      part
    ),
  );
}
