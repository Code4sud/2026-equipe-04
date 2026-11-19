import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import { SERIES_SIZE } from '../quiz/quizLogic';
import type { Badge, GameStatus, InstrumentSummary } from '../types';
import { gameEmoji } from './gameEmoji';
import { hubFr } from './hub.fr';
import { NeoSlot } from './NeoSlot';
import { XpBar } from './XpBar';
import './hub.css';

const t = hubFr;
const QUIZ_ID = 'onboarding';
const QUIZ_PATH = '/jeune/quiz';

type CardState = 'locked' | 'new' | 'progress' | 'done';

/** Une partie ouverte sans aucune réponse n’est pas encore « en cours » pour le jeune. */
function cardState(game: InstrumentSummary): CardState {
  if (game.locked) return 'locked';
  if (game.state === 'in_progress' && game.answered > 0) return 'progress';
  return game.completed_count > 0 ? 'done' : 'new';
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M8 4.6V8l2.3 1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StateChip({ state, game }: { state: CardState; game: InstrumentSummary }) {
  if (state === 'locked') {
    return (
      <span className="hub-chip hub-chip--locked">
        <span aria-hidden="true">🔒</span>
        <span aria-hidden="true">{t.card.locked}</span>
        <span className="visually-hidden">{t.card.lockedLabel}</span>
      </span>
    );
  }
  if (state === 'done') {
    return (
      <span className="hub-chip hub-chip--done">
        <span aria-hidden="true">✓</span>
        {t.card.done}
      </span>
    );
  }
  if (state === 'progress') {
    return (
      <span className="hub-chip hub-chip--progress">
        {t.card.inProgress}
        {game.total > 0 && <> · {t.card.progress(game.answered, game.total)}</>}
      </span>
    );
  }
  return (
    <span className="hub-chip hub-chip--new">
      <span aria-hidden="true">✦</span>
      {t.card.new}
    </span>
  );
}

/** `quizPending` : le quiz d’arrivée est rappelé plus haut, pas besoin de le redire ici. */
function GameCard({ game, quizPending }: { game: InstrumentSummary; quizPending: boolean }) {
  const state = cardState(game);
  const cta = state === 'progress' ? t.card.resume : state === 'done' ? t.card.replay : t.card.play;
  const canPlay = state !== 'locked' && (state !== 'done' || game.replayable);
  const titleId = `hub-game-${game.id}`;
  const ctaClass = `button button--small hub-card__cta${state === 'done' ? '' : ' button--primary'}`;

  return (
    <li className={`hub-card hub-card--${state}`}>
      <span className="hub-card__icon" aria-hidden="true">
        {gameEmoji(game.icon)}
      </span>
      <div className="hub-card__body">
        <div className="hub-card__head">
          <h3 id={titleId} className="hub-card__title">
            {game.title}
          </h3>
          <StateChip state={state} game={game} />
        </div>
        <p className="hub-card__tagline">{game.tagline}</p>
        {state === 'progress' && game.total > 0 && (
          <div
            className="hub-mini-bar"
            role="progressbar"
            aria-label={t.card.progressLabel(game.title)}
            aria-valuemin={0}
            aria-valuemax={game.total}
            aria-valuenow={game.answered}
          >
            <span style={{ width: `${(game.answered / game.total) * 100}%` }} />
          </div>
        )}
        <div className="hub-card__foot">
          <p className="hub-card__meta">
            <span className="hub-meta">
              <ClockIcon />
              <span className="visually-hidden">{t.card.durationLabel(game.duration_min)}</span>
              <span aria-hidden="true">{t.card.duration(game.duration_min)}</span>
            </span>
            {game.completed_count === 0 ? (
              <span className="hub-meta hub-meta--xp">
                <span className="visually-hidden">{t.card.xpLabel(game.xp)}</span>
                <span aria-hidden="true">{t.card.xp(game.xp)}</span>
              </span>
            ) : (
              game.completed_count > 1 && (
                <span className="hub-meta">{t.card.doneCount(game.completed_count)}</span>
              )
            )}
          </p>
          {canPlay && (
            <Link
              to={`/jeune/jeux/${game.id}`}
              className={ctaClass}
              aria-describedby={titleId}
            >
              {cta}
            </Link>
          )}
        </div>
        {state === 'locked' && !quizPending && (
          <p className="hub-card__lock">
            {t.card.lockedHint}{' '}
            <Link to={QUIZ_PATH} className="hub-card__quiz-link">
              {t.card.toQuiz}
            </Link>
          </p>
        )}
      </div>
    </li>
  );
}

function QuizCallout({ quiz }: { quiz: InstrumentSummary }) {
  // Commencé dès la première question vue, même passée : le quiz s'ouvre alors sur la reprise.
  const started = quiz.state === 'in_progress' && quiz.seen > 0;
  return (
    <section className="hub-quiz" aria-labelledby="hub-quiz-title">
      <span className="hub-quiz__icon" aria-hidden="true">
        {gameEmoji(quiz.icon)}
      </span>
      <div className="hub-quiz__body">
        <h2 id="hub-quiz-title">{t.quiz.title}</h2>
        {started && quiz.total > 0 && (
          <>
            <p className="hub-quiz__count">{t.quiz.progress(quiz.answered, quiz.total)}</p>
            <div
              className="hub-mini-bar"
              role="progressbar"
              aria-label={t.quiz.progressLabel}
              aria-valuemin={0}
              aria-valuemax={quiz.total}
              aria-valuenow={quiz.answered}
            >
              <span style={{ width: `${(quiz.answered / quiz.total) * 100}%` }} />
            </div>
          </>
        )}
        <p className="hub-quiz__hint">
          {started ? t.quiz.next(SERIES_SIZE) : t.quiz.format(quiz.total, SERIES_SIZE)} {t.quiz.hint}
        </p>
        {/* « Continuer » seul ne dit pas quoi : comme les cartes de jeu, le lien renvoie au titre. */}
        <Link
          to={QUIZ_PATH}
          className="button button--primary hub-quiz__cta"
          aria-describedby="hub-quiz-title"
        >
          {started ? t.quiz.resume : t.quiz.start}
        </Link>
      </div>
    </section>
  );
}

function BadgeItem({ badge }: { badge: Badge }) {
  return (
    <li className={`hub-badge${badge.earned ? '' : ' hub-badge--hidden'}`}>
      <span className="hub-badge__icon" aria-hidden="true">
        {gameEmoji(badge.icon)}
      </span>
      <strong className="hub-badge__label">{badge.label}</strong>
      <span className="hub-badge__state">
        {badge.earned ? (
          <>
            <span aria-hidden="true">✓ </span>
            {t.badges.earned}
          </>
        ) : (
          t.badges.toDiscover
        )}
      </span>
      <span className="hub-badge__description">{badge.description}</span>
    </li>
  );
}

export default function GamesHubPage() {
  const [status, setStatus] = useState<GameStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setStatus(await gameApi.status(signal));
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!status) return <Loading />;

  const { progress } = status;
  const quiz =
    status.instruments.find((game) => game.id === QUIZ_ID) ??
    status.instruments.find((game) => game.kind === 'quiz');
  const games = status.instruments.filter((game) => game !== quiz);
  const quizPending = quiz !== undefined && quiz.completed_count === 0;
  const earned = progress.badges.filter((badge) => badge.earned).length;

  return (
    <div className="scroll-area">
      <div className="page hub">
        <header className="page-head">
          <h1>{t.title}</h1>
          <p className="muted">{t.intro}</p>
          {/* Consentement donné à l'inscription : on rappelle simplement qui voit quoi. */}
          <p className="hub-shared">{t.shared}</p>
        </header>

        <section className="hub-level" aria-label={t.level(progress.level)}>
          <NeoSlot mood="wave" />
          <div className="hub-level__body">
            <p className="hub-level__kicker">{t.level(progress.level)}</p>
            <p className="hub-level__title">{progress.level_title}</p>
            <XpBar progress={progress} />
          </div>
        </section>

        {quiz && quizPending && <QuizCallout quiz={quiz} />}

        <section className="hub-section" aria-labelledby="hub-games-title">
          <h2 id="hub-games-title">{t.games}</h2>
          {games.length === 0 ? (
            <p className="empty">{t.empty}</p>
          ) : (
            <ul className="hub-grid">
              {games.map((game) => (
                <GameCard key={game.id} game={game} quizPending={quizPending} />
              ))}
            </ul>
          )}
        </section>

        {progress.badges.length > 0 && (
          <section className="hub-section" aria-labelledby="hub-badges-title">
            <div className="hub-section__head">
              <h2 id="hub-badges-title">{t.badges.title}</h2>
              <span className="count">{t.badges.count(earned, progress.badges.length)}</span>
            </div>
            {/* Défile à l’horizontale sur mobile : la zone se fait défiler au clavier. */}
            <div
              className="hub-badges"
              tabIndex={0}
              role="region"
              aria-labelledby="hub-badges-title"
            >
              <ul>
                {progress.badges.map((badge) => (
                  <BadgeItem key={badge.id} badge={badge} />
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
