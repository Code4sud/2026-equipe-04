import type { CSSProperties } from 'react';
import type { PsyCursor } from '../types';

/**
 * Barre décorative : le texte voisin porte déjà la valeur.
 * Bipolaire : remplissage depuis le centre. Unipolaire : depuis 0.
 * Plus la confiance est faible, plus le remplissage est pâle.
 */
export function CursorBar({ cursor }: { cursor: PsyCursor }) {
  const value = cursor.value;
  const bipolar = cursor.kind === 'bipolar';
  const style = (start: number, end: number) =>
    ({ '--bog-start': `${start}%`, '--bog-size': `${end - start}%` }) as CSSProperties;

  return (
    <div className="bog-bar-wrap" aria-hidden="true">
      <div className={`bog-bar bog-bar--${cursor.kind} bog-bar--${cursor.confidence}`}>
        {bipolar && <span className="bog-bar__mid" />}
        {value !== null && (
          <>
            <span
              className="bog-bar__fill"
              style={bipolar ? style(Math.min(value, 50), Math.max(value, 50)) : style(0, value)}
            />
            <span className="bog-bar__dot" style={{ '--bog-start': `${value}%` } as CSSProperties} />
          </>
        )}
      </div>
      {bipolar && (
        <div className="bog-bar__poles">
          <span>{cursor.low}</span>
          <span>{cursor.high}</span>
        </div>
      )}
    </div>
  );
}
