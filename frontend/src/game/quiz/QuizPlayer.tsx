import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ErrorState } from '../../components/Feedback';
import { ArchetypeBadge } from '../archetype/ArchetypeBadge';
import { frenchSpacing } from '../components/frenchSpacing';
import { QuestionCard } from '../components/QuestionCard';
import type { AnswerValue } from '../types';
import { isPending, useRunPlayer } from '../useRunPlayer';
import { NeoSlot } from './NeoSlot';
import { quizFr } from './quiz.fr';
import { QUIZ_ID, SERIES_SIZE, seriesMinutes, seriesSpot, sittingOrder, XP_PER_ANSWER } from './quizLogic';
import { QuizReveal } from './QuizReveal';
import { SeriesDots } from './SeriesDots';
import { XpCounter } from './XpCounter';

const t = quizFr;
/** Le temps de voir son choix s'allumer avant de passer à la question suivante. */
const PICK_DELAY_MS = 180;
/** « Continuer plus tard » mène à la discussion ; la fin d'une série, aux jeux, où le quiz attend. */
const LATER_PATH = '/jeune/discussion';
const HUB_PATH = '/jeune/jeux';

/** Titre d'écran qui prend le focus à l'affichage, pour les lecteurs d'écran. */
function ScreenTitle({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => ref.current?.focus({ preventScroll: true }), []);
  return (
    <h1 ref={ref} tabIndex={-1} className="quiz-title">
      {children}
    </h1>
  );
}

function Waiting({ text }: { text: string }) {
  return (
    <div className="quiz-screen quiz-screen--center" role="status">
      <NeoSlot mood="thinking" />
      <p>{text}</p>
    </div>
  );
}

/**
 * Le quiz d'arrivée : accueil, une question par écran dans un ordre tiré au hasard pour la partie,
 * par séries de 10 avec à chaque fois le choix de continuer ou de revenir plus tard, puis
 * révélation de l'archétype.
 */
export function QuizPlayer({ onAlreadyDone }: { onAlreadyDone: () => void }) {
  const player = useRunPlayer(QUIZ_ID, { shuffle: true });
  const navigate = useNavigate();
  const { instrument, items, index, current, answers, startedWith, reviewing } = player;
  const [welcomed, setWelcomed] = useState(false);
  /** Séries de cette séance après lesquelles le jeune a choisi de continuer. */
  const [continued, setContinued] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [direction, setDirection] = useState<'forward' | 'back'>('forward');
  const [pausing, setPausing] = useState(false);
  const [pauseError, setPauseError] = useState<string | null>(null);
  const pickTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(pickTimer.current), []);

  // Les séries comptent les questions vues depuis l'ouverture du quiz : elles repartent de zéro à
  // chaque reprise. Une fois toutes les questions vues, place à la fin (et à la revue des passées).
  const sitting = sittingOrder(items, answers, startedWith.seenIds);
  const unseen = items.filter((item) => !answers[item.id]).length;
  const seriesEnded = !reviewing && unseen > 0 && Math.floor(sitting.length / SERIES_SIZE) > continued;

  // Chaque écran commence en haut, même si le précédent avait défilé (petits téléphones).
  const screenKey = `${welcomed}:${seriesEnded}:${continued}:${index}:${Boolean(player.result)}`;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [screenKey]);

  useEffect(() => {
    if (player.errorCode === 'already_completed') onAlreadyDone();
  }, [player.errorCode, onAlreadyDone]);

  async function leave(to: string) {
    setPausing(true);
    setPauseError(null);
    try {
      await player.pause();
      navigate(to, { replace: true });
    } catch {
      setPauseError(t.question.pauseError);
      setPausing(false);
    }
  }

  if (player.errorCode === 'already_completed') return <Waiting text={t.loading} />;
  if (player.error && !instrument) {
    return (
      <div className="quiz-screen quiz-screen--center">
        <ErrorState message={player.error} onRetry={() => void player.reload()} />
        <Link className="text-link" to={LATER_PATH}>
          {t.leave}
        </Link>
      </div>
    );
  }
  if (!instrument) return <Waiting text={t.loading} />;

  if (player.result) {
    const { result } = player;
    return (
      <QuizReveal
        mode="reveal"
        archetype={result.archetype}
        highlights={result.highlights}
        progress={result.progress}
        badges={result.new_badges}
        xpGained={result.xp_gained}
        leveledUp={result.leveled_up}
      />
    );
  }
  if (player.finishing) return <Waiting text={t.end.thinking} />;

  const total = items.length;
  const resumed = startedWith.seen > 0;
  const missing = Math.max(0, (instrument.min_answers ?? 0) - player.answeredCount);
  // Avant la révélation, il faut voir toutes les questions et avoir assez de réponses : après
  // beaucoup de questions passées, il en faut plus que les jamais vues.
  const toReveal = Math.max(unseen, missing);
  const pendingCount = items.filter((item) => isPending(item, answers)).length;
  const xp = startedWith.answered * XP_PER_ANSWER + player.xpGained;
  const laterButton = (label: string) => (
    <button type="button" className="link-button" disabled={pausing} onClick={() => void leave(LATER_PATH)}>
      {pausing ? t.question.pausing : label}
    </button>
  );
  const pauseAlert = pauseError && (
    <p className="form-error" role="alert">
      {pauseError}
    </p>
  );

  function start() {
    setWelcomed(true);
    // Le temps passé sur l'accueil ne compte pas dans celui de la première question.
    player.markShown();
  }

  function cancelPick() {
    window.clearTimeout(pickTimer.current);
    pickTimer.current = undefined;
    setPicked(null);
  }

  function startReview() {
    cancelPick();
    player.clearError();
    setDirection('forward');
    player.review();
  }

  function backToLastQuestion() {
    setDirection('back');
    player.goTo(total - 1);
  }

  // --- Accueil ---
  if (!resumed && !welcomed) {
    return (
      <div className="quiz-screen quiz-screen--center quiz-welcome">
        <NeoSlot mood="wave" />
        <p className="quiz-kicker">{t.welcome.kicker}</p>
        <ScreenTitle>{frenchSpacing(t.welcome.title)}</ScreenTitle>
        <p className="quiz-bubble">{frenchSpacing(instrument.intro ?? t.welcome.intro)}</p>
        <ul className="quiz-rules plain-list" aria-label={t.welcome.rulesLabel}>
          <li>
            <span aria-hidden="true">🎲</span>
            {t.welcome.series(SERIES_SIZE)}
          </li>
          <li>
            <span aria-hidden="true">⏱️</span>
            {t.welcome.duration(seriesMinutes(instrument.duration_min, total))}
          </li>
          {t.welcome.rules.map((rule) => (
            <li key={rule.text}>
              <span aria-hidden="true">{rule.icon}</span>
              {rule.text}
            </li>
          ))}
        </ul>
        <p className="quiz-transparency">{frenchSpacing(t.welcome.transparency)}</p>
        {pauseAlert}
        <div className="quiz-actions">
          <button type="button" className="button button--primary" onClick={start}>
            {t.welcome.start}
          </button>
          {laterButton(t.welcome.later)}
        </div>
      </div>
    );
  }

  // --- Reprise : une nouvelle série commence ---
  if (resumed && !welcomed && unseen > 0) {
    return (
      <div className="quiz-screen quiz-screen--center quiz-welcome">
        <NeoSlot mood="wave" />
        <p className="quiz-kicker">{t.resume.kicker}</p>
        <ScreenTitle>{frenchSpacing(t.resume.title)}</ScreenTitle>
        <p className="quiz-bubble">
          {frenchSpacing(t.resume.text(startedWith.answered, total, unseen, toReveal, SERIES_SIZE))}
        </p>
        {pauseAlert}
        <div className="quiz-actions">
          <button type="button" className="button button--primary" onClick={start}>
            {t.resume.start}
          </button>
          {laterButton(t.welcome.later)}
        </div>
      </div>
    );
  }

  // --- Fin du parcours ---
  if (player.atEnd) {
    const notEnough = missing > 0 || player.errorCode === 'not_enough_answers';
    return (
      <div className="quiz-screen quiz-screen--center">
        <NeoSlot mood={notEnough ? 'thinking' : 'cheer'} />
        {notEnough ? (
          <>
            <ScreenTitle>{t.end.missingTitle}</ScreenTitle>
            <p className="quiz-bubble" role="status">
              {frenchSpacing(missing > 0 ? t.end.missing(missing) : (player.error ?? ''))}
            </p>
            <p className="quiz-count">{t.end.count(player.answeredCount, total)}</p>
            {pauseAlert}
            <div className="quiz-actions">
              <button type="button" className="button button--primary" onClick={startReview}>
                {t.end.reviewMissing}
              </button>
              {laterButton(t.question.later)}
            </div>
          </>
        ) : (
          <>
            <ScreenTitle>{frenchSpacing(t.end.title)}</ScreenTitle>
            <p className="quiz-bubble">{frenchSpacing(instrument.outro ?? t.end.text)}</p>
            <p className="quiz-count">{t.end.count(player.answeredCount, total)}</p>
            {player.error && (
              <p className="form-error" role="alert">
                {player.error}
              </p>
            )}
            {pauseAlert}
            <div className="quiz-actions">
              <button type="button" className="button button--primary" onClick={() => void player.finish()}>
                {t.end.reveal}
              </button>
              {pendingCount > 0 && (
                <>
                  <p className="quiz-note">{t.end.skipped(pendingCount)}</p>
                  <button type="button" className="link-button" onClick={startReview}>
                    {t.end.review}
                  </button>
                </>
              )}
              <button type="button" className="link-button" onClick={backToLastQuestion}>
                {t.end.back}
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  // --- Fin d'une série : 10 de plus, ou une pause ---
  if (seriesEnded) {
    // Un double appui commencé sur la dernière question de la série ne choisit rien ici.
    const unlessJustShown = (action: () => void) => () => {
      if (!player.justShown()) action();
    };
    return (
      <div className="quiz-screen quiz-screen--center quiz-break">
        <NeoSlot mood="cheer" />
        <ScreenTitle>{frenchSpacing(t.series.title)}</ScreenTitle>
        <p className="quiz-bubble">{frenchSpacing(t.series.text)}</p>
        <div className="quiz-mystery">
          {/* L'archétype reste une surprise jusqu'à la révélation : le badge garde son « ? ». */}
          <ArchetypeBadge archetype={null} />
          <div className="quiz-mystery__text">
            <p className="quiz-mystery__left">{t.series.left(toReveal)}</p>
            <p className="quiz-mystery__xp">{t.xp.label(xp)}</p>
          </div>
        </div>
        {pauseAlert}
        <div className="quiz-actions">
          <button
            type="button"
            className="button button--primary"
            disabled={pausing}
            onClick={unlessJustShown(() => {
              setContinued(Math.floor(sitting.length / SERIES_SIZE));
              setDirection('forward');
              // Le temps passé sur cet écran ne compte pas dans celui de la question suivante.
              player.markShown();
            })}
          >
            {t.series.more(Math.min(SERIES_SIZE, unseen), unseen <= SERIES_SIZE)}
          </button>
          <button
            type="button"
            className="link-button"
            disabled={pausing}
            onClick={unlessJustShown(() => void leave(HUB_PATH))}
          >
            {pausing ? t.question.pausing : t.series.later}
          </button>
        </div>
      </div>
    );
  }

  if (!current) return <Waiting text={t.loading} />;

  // --- Une question ---
  const item = current;
  const stored = answers[item.id];
  const alreadyAnswered = stored !== undefined && !stored.skipped;
  const spot = seriesSpot(sitting, continued, item.id, stored !== undefined, unseen);
  const step = reviewing
    ? t.question.reviewing
    : spot.position !== null
      ? t.question.series(spot.position + 1, spot.size)
      : t.question.earlier(Boolean(stored?.skipped));

  // Le hook choisit la question suivante, revue des questions passées comprise.
  function commit(value: AnswerValue, responseMs: number) {
    if (!player.answer(value, responseMs)) return;
    setDirection('forward');
  }

  function handleAnswer(value: AnswerValue) {
    // Un appui juste après l'affichage termine un double appui commencé sur l'écran d'avant.
    if (pickTimer.current !== undefined || player.justShown()) return;
    // Le temps de réponse s'arrête à l'appui, pas après l'animation du choix.
    const responseMs = player.elapsed();
    if (typeof value !== 'string') {
      commit(value, responseMs);
      return;
    }
    setPicked(value);
    pickTimer.current = window.setTimeout(() => {
      pickTimer.current = undefined;
      setPicked(null);
      commit(value, responseMs);
    }, PICK_DELAY_MS);
  }

  function handleSkip() {
    cancelPick();
    if (!player.skip()) return;
    setDirection('forward');
  }

  function handleNext() {
    cancelPick();
    setDirection('forward');
    player.next();
  }

  function handleBack() {
    cancelPick();
    setDirection('back');
    player.back();
  }

  return (
    <div className="quiz-screen quiz-screen--question">
      <div className="quiz-bar">
        {laterButton(t.question.later)}
        <XpCounter value={xp} />
      </div>
      {/* Pas de série pendant la revue des questions passées, ni pour une question d'une séance
          précédente, revue avec « Retour ». */}
      {!reviewing && spot.position !== null && <SeriesDots {...spot} />}
      <p className="quiz-meta">
        <span id="quiz-step">{step}</span>
        <span className="quiz-meta__count">{t.question.answered(player.answeredCount, total)}</span>
      </p>
      {pauseAlert}
      {player.saveFailed && (
        <p className="notice" role="status">
          {t.question.saveError}
        </p>
      )}
      {reviewing && missing === 0 && (
        <div className="quiz-enough" role="status">
          <p>{t.question.enough}</p>
          <button type="button" className="button button--small button--primary" onClick={() => player.goTo(total)}>
            {t.question.toEnd}
          </button>
        </div>
      )}
      <div key={item.id} className={`quiz-slide quiz-slide--${direction}`}>
        <QuestionCard
          key={item.id}
          item={item}
          scale={instrument.scale}
          value={picked ?? stored?.value}
          onAnswer={handleAnswer}
          autoFocus
          describedBy="quiz-step"
        />
      </div>
      <div className="quiz-nav">
        <button type="button" className="button quiz-nav__back" disabled={index === 0} onClick={handleBack}>
          <span aria-hidden="true">←</span> {t.question.back}
        </button>
        {alreadyAnswered ? (
          <button type="button" className="button quiz-nav__next" onClick={handleNext}>
            {t.question.next} <span aria-hidden="true">→</span>
          </button>
        ) : (
          <button type="button" className="button quiz-nav__next" onClick={handleSkip}>
            {t.question.skip} <span aria-hidden="true">→</span>
          </button>
        )}
      </div>
    </div>
  );
}
