import { useState } from 'react';
import { useCountUp } from './motion';
import { quizFr } from './quiz.fr';

const t = quizFr.xp;

/** Compteur d'XP du quiz : le nombre défile et un « +2 » s'envole à chaque réponse. */
export function XpCounter({ value }: { value: number }) {
  const shown = useCountUp(value, { duration: 450 });
  const [previous, setPrevious] = useState(value);
  const [bump, setBump] = useState<{ key: number; gain: number } | null>(null);

  if (value !== previous) {
    setPrevious(value);
    if (value > previous) setBump({ key: (bump?.key ?? 0) + 1, gain: value - previous });
  }

  return (
    <div className="quiz-xp">
      <span className="quiz-xp__value" aria-hidden="true">
        {shown}
        <span className="quiz-xp__unit">{t.unit}</span>
      </span>
      <span className="visually-hidden" aria-live="polite" aria-atomic="true">
        {bump ? t.announce(bump.gain, value) : t.label(value)}
      </span>
      {bump && (
        <span key={bump.key} className="quiz-xp__bump" aria-hidden="true">
          {t.gain(bump.gain)}
        </span>
      )}
    </div>
  );
}
