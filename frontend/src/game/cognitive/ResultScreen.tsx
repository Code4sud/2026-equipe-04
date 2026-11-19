import { Link } from 'react-router-dom';
import type { PublicInstrument, RunResult } from '../types';
import { cogFr } from './cognitive.fr';
import type { GameSummary } from './results';
import { GAMES_PATH, GameTop, NeoSays } from './ui';

const t = cogFr.result;
const BADGE_ICONS: Record<string, string> = {
  paw: '🐾',
  dice: '🎲',
  map: '🗺️',
  star: '⭐',
  stars: '✨',
  flag: '🚩',
};

export function ResultScreen({
  instrument,
  result,
  summary,
  record,
  onReplay,
}: {
  instrument: PublicInstrument;
  result: RunResult;
  summary: GameSummary;
  record: 'new' | 'first' | null;
  onReplay: () => void;
}) {
  const { progress } = result;
  const span = Math.max(1, progress.next_level_xp - progress.level_xp);
  const filled = Math.min(100, Math.max(0, ((progress.xp - progress.level_xp) / span) * 100));

  return (
    <section className="cog-intro cog-result" aria-labelledby="cog-result-title">
      <GameTop title={instrument.title} />
      <NeoSays mood="cheer" big live={false}>
        {instrument.outro ?? t.title}
      </NeoSays>
      <h2 id="cog-result-title" className="cog-result__title">
        {t.title}
      </h2>
      {record && <p className="cog-record">{record === 'new' ? t.newRecord : t.firstRecord}</p>}

      {summary.stats.length ? (
        <dl className="cog-stats">
          {summary.stats.map((stat) => (
            <div key={stat.label} className="cog-stat">
              <dt>{stat.label}</dt>
              <dd>
                <b>{stat.value}</b>
                {stat.unit && <span> {stat.unit}</span>}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="cog-card">{summary.empty}</p>
      )}

      <div className="cog-card cog-xp">
        {result.xp_gained > 0 && (
          <p className="cog-xp__gain">
            {t.xp(result.xp_gained)} <span className="cog-small muted">{t.xpLabel}</span>
          </p>
        )}
        <p className={result.leveled_up ? 'cog-xp__level cog-xp__level--up' : 'cog-xp__level'}>
          {result.leveled_up
            ? t.levelUp(progress.level, progress.level_title)
            : t.level(progress.level, progress.level_title)}
        </p>
        <div
          className="cog-meter"
          role="progressbar"
          aria-label={t.level(progress.level, progress.level_title)}
          aria-valuemin={progress.level_xp}
          aria-valuemax={progress.next_level_xp}
          aria-valuenow={progress.xp}
        >
          <span style={{ width: `${filled}%` }} />
        </div>
        <p className="cog-small muted">{t.toNext(Math.max(0, progress.next_level_xp - progress.xp))}</p>
      </div>

      {result.new_badges.length > 0 && (
        <div className="cog-card">
          <h2>{t.badges}</h2>
          <ul className="cog-badges">
            {result.new_badges.map((badge) => (
              <li key={badge.id}>
                <span className="cog-badges__icon" aria-hidden="true">
                  {BADGE_ICONS[badge.icon] ?? '🏅'}
                </span>
                <span>
                  <strong>{badge.label}</strong>
                  <small>{badge.description}</small>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="cog-actions cog-actions--end">
        <button type="button" className="button button--primary" onClick={onReplay}>
          {t.replay}
        </button>
        <Link className="button" to={GAMES_PATH}>
          {t.back}
        </Link>
      </div>
    </section>
  );
}
