import type { Progress } from '../types';
import { hubFr } from './hub.fr';
import './common.css';

const t = hubFr;

/** Barre d’XP vers le niveau suivant, avec le reste à gagner écrit en clair. */
export function XpBar({ progress }: { progress: Progress }) {
  const span = Math.max(progress.next_level_xp - progress.level_xp, 1);
  const done = Math.min(Math.max(progress.xp - progress.level_xp, 0), span);
  const missing = Math.max(progress.next_level_xp - progress.xp, 0);

  return (
    <div className="hub-xp">
      <div
        className="hub-xp__track"
        role="progressbar"
        aria-label={t.xpLabel}
        aria-valuemin={progress.level_xp}
        aria-valuemax={progress.next_level_xp}
        aria-valuenow={progress.xp}
        aria-valuetext={t.xpValue(progress.xp, progress.next_level_xp, progress.level)}
      >
        <span style={{ width: `${(done / span) * 100}%` }} />
      </div>
      <p className="hub-xp__label">
        <span className="hub-xp__count">{t.xpCount(progress.xp, progress.next_level_xp)}</span>
        <span>{t.xpMissing(missing, progress.level + 1)}</span>
      </p>
    </div>
  );
}
