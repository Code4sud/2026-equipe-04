import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ErrorState } from '../../components/Feedback';
import { frenchSpacing } from '../components/frenchSpacing';
import { QuestionCard } from '../components/QuestionCard';
import type { AnswerValue } from '../types';
import { useRunPlayer } from '../useRunPlayer';
import { ChapterProgress } from './ChapterProgress';
import { NeoSlot } from './NeoSlot';
import { quizFr } from './quiz.fr';
import { chapterOf, isPending, nextPendingIndex, QUIZ_ID, XP_PER_ANSWER } from './quizLogic';
import { QuizReveal } from './QuizReveal';
import { XpCounter } from './XpCounter';

const t = quizFr;
/** Le temps de voir son choix s'allumer avant de passer à la question suivante. */
const PICK_DELAY_MS = 180;

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

/** Le quiz d'arrivée : accueil, chapitres, une question par écran, puis révélation du clan. */
export function QuizPlayer({ onAlreadyDone }: { onAlreadyDone: () => void }) {
  const player = useRunPlayer(QUIZ_ID);
  const navigate = useNavigate();
  const { instrument, items, index, current, answers, startedWith } = player;
  const [welcomed, setWelcomed] = useState(false);
  const [introduced, setIntroduced] = useState<ReadonlySet<string>>(() => new Set());
  const [reviewing, setReviewing] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [direction, setDirection] = useState<'forward' | 'back'>('forward');
  const [pausing, setPausing] = useState(false);
  const [pauseError, setPauseError] = useState<string | null>(null);
  const pickTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(pickTimer.current), []);

  // Chaque écran commence en haut, même si le précédent avait défilé (petits téléphones).
  const screenKey = `${welcomed}:${introduced.size}:${index}:${Boolean(player.result)}`;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [screenKey]);

  useEffect(() => {
    if (player.errorCode === 'already_completed') onAlreadyDone();
  }, [player.errorCode, onAlreadyDone]);

  async function leave() {
    setPausing(true);
    setPauseError(null);
    try {
      await player.pause();
      navigate('/jeune/discussion', { replace: true });
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
        <Link className="text-link" to="/jeune/discussion">
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
        clan={result.clan}
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
  const pendingCount = items.filter((item) => isPending(item, answers)).length;
  const xp = startedWith.answered * XP_PER_ANSWER + player.xpGained;
  const laterButton = (label: string) => (
    <button type="button" className="link-button" disabled={pausing} onClick={() => void leave()}>
      {pausing ? t.question.pausing : label}
    </button>
  );
  const pauseAlert = pauseError && (
    <p className="form-error" role="alert">
      {pauseError}
    </p>
  );

  function cancelPick() {
    window.clearTimeout(pickTimer.current);
    pickTimer.current = undefined;
    setPicked(null);
  }

  function startReview() {
    cancelPick();
    player.clearError();
    setReviewing(true);
    setDirection('forward');
    player.goTo(nextPendingIndex(items, answers, -1));
  }

  function backToLastQuestion() {
    const chapter = items[total - 1]?.chapter;
    if (chapter) setIntroduced((done) => new Set(done).add(chapter));
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
            <span aria-hidden="true">⏱️</span>
            {t.welcome.duration(instrument.duration_min)}
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
          <button type="button" className="button button--primary" onClick={() => setWelcomed(true)}>
            {t.welcome.start}
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

  if (!current) return <Waiting text={t.loading} />;
  const info = chapterOf(instrument, current);

  // --- Intermède de chapitre (ou reprise) ---
  if (info && !reviewing && !introduced.has(info.chapter.id)) {
    const resuming = resumed && introduced.size === 0;
    const chapterId = info.chapter.id;
    return (
      <div className="quiz-screen quiz-screen--center quiz-chapter">
        <NeoSlot mood={resuming ? 'wave' : 'happy'} />
        {resuming && <p className="quiz-kicker">{t.chapter.resumeKicker}</p>}
        <p className="quiz-chapter__count">{t.chapter.count(info.position, info.total)}</p>
        <ScreenTitle>{info.chapter.title}</ScreenTitle>
        {info.chapter.intro && <p className="quiz-bubble">{frenchSpacing(info.chapter.intro)}</p>}
        {resuming && <p className="quiz-note">{t.chapter.resumeText(startedWith.answered)}</p>}
        <ol className="quiz-chapter__steps plain-list" aria-hidden="true">
          {(instrument.chapters ?? []).map((chapter, position) => (
            <li
              key={chapter.id}
              className={
                position + 1 < info.position ? 'is-done' : position + 1 === info.position ? 'is-current' : ''
              }
            />
          ))}
        </ol>
        {pauseAlert}
        <div className="quiz-actions">
          <button
            type="button"
            className="button button--primary"
            onClick={() => setIntroduced((done) => new Set(done).add(chapterId))}
          >
            {resuming ? t.chapter.resume : t.chapter.start}
          </button>
          {laterButton(t.question.later)}
        </div>
      </div>
    );
  }

  // --- Une question ---
  const item = current;
  const stored = answers[item.id];
  const alreadyAnswered = stored !== undefined && !stored.skipped;
  const chapterTitle = info?.chapter.title ?? '';

  function afterLeaving(itemId: string) {
    if (reviewing) player.goTo(nextPendingIndex(items, answers, index, itemId));
  }

  function commit(value: AnswerValue) {
    setDirection('forward');
    player.answer(value);
    afterLeaving(item.id);
  }

  function handleAnswer(value: AnswerValue) {
    if (pickTimer.current !== undefined) return;
    if (typeof value !== 'string') {
      commit(value);
      return;
    }
    setPicked(value);
    pickTimer.current = window.setTimeout(() => {
      pickTimer.current = undefined;
      setPicked(null);
      commit(value);
    }, PICK_DELAY_MS);
  }

  function handleSkip() {
    cancelPick();
    setDirection('forward');
    player.skip();
    afterLeaving(item.id);
  }

  function handleNext() {
    cancelPick();
    setDirection('forward');
    player.goTo(reviewing ? nextPendingIndex(items, answers, index) : index + 1);
  }

  function handleBack() {
    cancelPick();
    const chapter = items[index - 1]?.chapter;
    if (chapter) setIntroduced((done) => new Set(done).add(chapter));
    setDirection('back');
    player.back();
  }

  return (
    <div className="quiz-screen quiz-screen--question">
      <div className="quiz-bar">
        {laterButton(t.question.later)}
        <XpCounter value={xp} />
      </div>
      <ChapterProgress
        instrument={instrument}
        index={index}
        label={t.question.progressLabel(index + 1, total, chapterTitle)}
      />
      <p className="quiz-meta">
        <span>{chapterTitle}</span>
        <span className="quiz-meta__count">{t.question.progress(index + 1, total)}</span>
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
          item={item}
          scale={instrument.scale}
          value={picked ?? stored?.value}
          onAnswer={handleAnswer}
          autoFocus
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
