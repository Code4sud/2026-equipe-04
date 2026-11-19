import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { frenchSpacing } from '../components/frenchSpacing';
import type { Badge, Clan, Progress, YouthTrait } from '../types';
import { ClanCrest } from './ClanCrest';
import { useCountUp, usePrefersReducedMotion } from './motion';
import { NeoSlot } from './NeoSlot';
import { quizFr } from './quiz.fr';
import { badgeEmoji } from './quizLogic';

const t = quizFr.reveal;
const SUSPENSE_MS = 1400;

interface Props {
  /** `reveal` juste après le quiz, `summary` quand on rouvre un quiz déjà terminé. */
  mode: 'reveal' | 'summary';
  clan: Clan | null;
  highlights: YouthTrait[];
  progress: Progress;
  /** Badges à montrer : les nouveaux après le quiz, tous ceux gagnés dans le résumé. */
  badges: Badge[];
  xpGained?: number;
  leveledUp?: boolean;
}

function Highlight({ trait }: { trait: YouthTrait }) {
  const bipolar = trait.kind === 'bipolar' && trait.low && trait.high && trait.value !== null;
  return (
    <li className="quiz-highlight">
      <span className="quiz-highlight__group">{t.groups[trait.group] ?? ''}</span>
      <strong className="quiz-highlight__label">{trait.label ?? t.between}</strong>
      {bipolar && (
        <span className="quiz-highlight__scale" aria-hidden="true">
          <span>{trait.low}</span>
          <span className="quiz-highlight__track">
            <span className="quiz-highlight__dot" style={{ left: `${trait.value}%` }} />
          </span>
          <span>{trait.high}</span>
        </span>
      )}
    </li>
  );
}

function LevelCard({ progress, xpGained = 0, leveledUp }: Pick<Props, 'progress' | 'xpGained' | 'leveledUp'>) {
  const total = useCountUp(progress.xp, { from: progress.xp - xpGained, duration: 1200 });
  const span = Math.max(1, progress.next_level_xp - progress.level_xp);
  const ratio = Math.min(1, Math.max(0, (progress.xp - progress.level_xp) / span));
  const [filled, setFilled] = useState(0);

  // La barre se remplit après l'affichage, pour qu'on la voie monter.
  useEffect(() => {
    const frame = requestAnimationFrame(() => setFilled(ratio));
    return () => cancelAnimationFrame(frame);
  }, [ratio]);

  return (
    <div className="quiz-level">
      {xpGained > 0 && <p className="quiz-level__bonus">{t.bonus(xpGained)}</p>}
      <p className="quiz-level__total">{t.total(total)}</p>
      {leveledUp && <p className="quiz-level__up">{t.levelUp}</p>}
      <p className="quiz-level__name">{t.level(progress.level, progress.level_title)}</p>
      <div className="quiz-level__bar" aria-hidden="true">
        <span style={{ width: `${filled * 100}%` }} />
      </div>
      <p className="quiz-level__next">{t.nextLevel(progress.next_level_xp - progress.xp)}</p>
    </div>
  );
}

/** Cérémonie de révélation du clan, ou rappel du résultat quand le quiz est déjà fait. */
export function QuizReveal({ mode, clan, highlights, progress, badges, xpGained, leveledUp }: Props) {
  const reduced = usePrefersReducedMotion();
  const [suspense, setSuspense] = useState(mode === 'reveal' && !reduced);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!suspense) return;
    const timer = window.setTimeout(() => setSuspense(false), SUSPENSE_MS);
    return () => window.clearTimeout(timer);
  }, [suspense]);

  useEffect(() => {
    if (!suspense) heading.current?.focus({ preventScroll: true });
  }, [suspense]);

  if (suspense) {
    return (
      <div className="quiz-screen quiz-screen--center" role="status">
        <NeoSlot mood="thinking" />
        <p className="quiz-suspense">{t.suspense}</p>
      </div>
    );
  }

  return (
    <div className={`quiz-screen quiz-reveal quiz-reveal--${mode}`}>
      <header className="quiz-reveal__head">
        <p className="quiz-kicker">{mode === 'summary' ? quizFr.done.kicker : t.kicker}</p>
        {clan ? (
          <>
            <div className="quiz-reveal__crest">
              <ClanCrest icon={clan.icon} label={t.crest(clan.name)} />
              <NeoSlot mood="cheer" />
            </div>
            <h1 ref={heading} tabIndex={-1}>
              {clan.name}
            </h1>
            <p className="quiz-reveal__motto">{frenchSpacing(`« ${clan.motto} »`)}</p>
            <p className="quiz-reveal__description">{frenchSpacing(clan.description)}</p>
          </>
        ) : (
          <>
            <NeoSlot mood="thinking" />
            <h1 ref={heading} tabIndex={-1}>
              {t.noClanTitle}
            </h1>
            <p className="quiz-reveal__description">{t.noClan}</p>
          </>
        )}
        {mode === 'summary' && <p className="quiz-reveal__intro">{frenchSpacing(quizFr.done.intro)}</p>}
      </header>

      {highlights.length > 0 && (
        <section className="quiz-reveal__section" aria-labelledby="quiz-highlights-title">
          <h2 id="quiz-highlights-title">{t.highlightsTitle}</h2>
          <ul className="quiz-highlights plain-list">
            {highlights.map((trait) => (
              <Highlight key={trait.id} trait={trait} />
            ))}
          </ul>
          <p className="quiz-reveal__hint">{frenchSpacing(t.highlightsHint)}</p>
        </section>
      )}

      <section className="quiz-reveal__section quiz-rewards" aria-labelledby="quiz-rewards-title">
        <h2 id="quiz-rewards-title">{t.rewardsTitle}</h2>
        <LevelCard progress={progress} xpGained={xpGained} leveledUp={leveledUp} />
        {badges.length > 0 && (
          <>
            <h3>{mode === 'summary' ? quizFr.done.badgesTitle : t.badgesTitle}</h3>
            <ul className="quiz-badges plain-list">
              {badges.map((badge) => (
                <li key={badge.id} className="quiz-badge">
                  <span className="quiz-badge__icon" aria-hidden="true">
                    {badgeEmoji(badge.icon)}
                  </span>
                  <span>
                    <strong>{badge.label}</strong>
                    <small>{badge.description}</small>
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <div className="quiz-actions">
        <Link className="button button--primary" to="/jeune/fiche">
          {t.sheet}
        </Link>
        <Link className="button" to="/jeune/jeux">
          {t.games}
        </Link>
      </div>
    </div>
  );
}
