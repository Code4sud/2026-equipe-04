import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorState, Loading } from '../../components/Feedback';
import { QuestionCard } from '../components/QuestionCard';
import { gameFr } from '../content.fr';
import { gameEmoji } from '../hub/gameEmoji';
import { NeoSlot } from '../hub/NeoSlot';
import type { Chapter } from '../types';
import { useRunPlayer } from '../useRunPlayer';
import { RunResults } from './RunResults';
import { playFr } from './play.fr';
import './play.css';

const t = playFr;
const HUB_PATH = '/jeune/jeux';

interface Props {
  instrumentId: string;
  /** Où revenir en quittant la partie : le hub par défaut. */
  exitTo?: string;
  /** La psychologue voit les réponses : on le dit avant de commencer. */
  shared?: boolean | null;
  /** Parties déjà terminées : une partie rejouée ne promet pas l’XP de la première fois. */
  completedBefore?: number;
}

function TopBar({
  label,
  onLeave,
  leaving,
  xp,
}: {
  label: string;
  onLeave: () => void;
  leaving: boolean;
  xp?: number;
}) {
  return (
    <div className="play-top">
      <button
        type="button"
        className="link-button play-top__leave"
        onClick={onLeave}
        disabled={leaving}
      >
        <span aria-hidden="true">← </span>
        {label}
      </button>
      {xp !== undefined && xp > 0 && (
        <span className="play-xp" aria-live="polite" aria-atomic="true">
          <span aria-hidden="true">{t.question.xp(xp)}</span>
          <span className="visually-hidden">{t.question.xpLabel(xp)}</span>
        </span>
      )}
    </div>
  );
}

/** Déroulé d’un questionnaire : accueil, questions par étapes, pause, fin et résultat. */
export function QuestionnairePlayer({
  instrumentId,
  exitTo = HUB_PATH,
  shared = null,
  completedBefore = 0,
}: Props) {
  const player = useRunPlayer(instrumentId);
  const { instrument, run, items, index, current, answers, result, reviewing } = player;
  const navigate = useNavigate();
  const [started, setStarted] = useState(false);
  const [seenChapters, setSeenChapters] = useState<ReadonlySet<string>>(() => new Set());
  const [leaving, setLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const focusTarget = useRef<HTMLElement | null>(null);
  const setFocusTarget = (node: HTMLElement | null) => {
    focusTarget.current = node;
  };

  const chapters = useMemo(() => instrument?.chapters ?? [], [instrument]);
  const chapterPosition = current?.chapter
    ? chapters.findIndex((chapter) => chapter.id === current.chapter)
    : -1;

  // Une étape qui commence s’annonce une fois, si elle a un mot d’intro. Pendant la revue des
  // questions passées, on va droit aux questions.
  const pendingChapter: Chapter | null = useMemo(() => {
    if (!started || reviewing || !current?.chapter || seenChapters.has(current.chapter)) return null;
    if (index > 0 && items[index - 1]?.chapter === current.chapter) return null;
    const chapter = chapters.find((entry) => entry.id === current.chapter);
    return chapter?.intro ? chapter : null;
  }, [started, reviewing, current, index, items, chapters, seenChapters]);

  const screen = !started
    ? 'intro'
    : pendingChapter
      ? 'chapter'
      : player.atEnd
        ? 'end'
        : 'question';
  const screenKey =
    screen === 'question'
      ? `question:${current?.id}`
      : screen === 'chapter'
        ? `chapter:${pendingChapter?.id}`
        : screen;

  // Une question place elle-même le focus sur son énoncé (QuestionCard autoFocus) : seuls
  // l'accueil, les étapes et la fin ont une cible ici.
  useEffect(() => {
    if (!instrument || result) return;
    window.scrollTo({ top: 0 });
    focusTarget.current?.focus({ preventScroll: true });
  }, [screenKey, instrument, result]);

  async function leave() {
    setLeaveError(null);
    if (!run) {
      navigate(exitTo);
      return;
    }
    setLeaving(true);
    try {
      await player.pause();
      navigate(exitTo);
    } catch {
      setLeaveError(t.pauseError);
      setLeaving(false);
    }
  }

  if (player.error && !instrument) {
    return <ErrorState message={player.error} onRetry={() => void player.reload()} />;
  }
  if (!instrument) return <Loading />;

  if (result) {
    return (
      <RunResults
        instrument={instrument}
        result={result}
        answerXp={player.xpGained}
        exitTo={exitTo}
      />
    );
  }

  const total = items.length;
  const answeredCount = player.answeredCount;
  const topBar = (
    <TopBar label={t.pause} onLeave={() => void leave()} leaving={leaving} xp={player.xpGained} />
  );
  const leaveNotice = leaveError && (
    <p className="form-error" role="alert">
      {leaveError}
    </p>
  );
  const progress = (
    <div className="play-progress">
      <div className="play-progress__bar" aria-hidden="true">
        <span style={{ width: `${(Math.min(index, total) / Math.max(total, 1)) * 100}%` }} />
      </div>
      <p id="play-progress-label" className="play-progress__label">
        {t.question.progress(Math.min(index + 1, total), total)}
      </p>
    </div>
  );

  if (screen === 'intro') {
    const resuming = Object.keys(answers).length > 0;
    return (
      <div className="play play--intro">
        <TopBar label={t.backToHub} onLeave={() => void leave()} leaving={leaving} />
        {leaveNotice}
        <div className="play-stage">
          <div className="play-hero">
            <span className="play-hero__icon" aria-hidden="true">
              {gameEmoji(instrument.icon)}
            </span>
            <h1 ref={setFocusTarget} tabIndex={-1}>
              {instrument.title}
            </h1>
            <p className="play-hero__tagline">{instrument.tagline}</p>
            <ul className="play-meta">
              <li>
                <span aria-hidden="true">{t.intro.duration(instrument.duration_min)}</span>
                <span className="visually-hidden">
                  {t.intro.durationLabel(instrument.duration_min)}
                </span>
              </li>
              <li>{t.intro.questions(total)}</li>
              {completedBefore === 0 && (
                <li className="play-meta__xp">
                  <span aria-hidden="true">{t.intro.xp(instrument.xp)}</span>
                  <span className="visually-hidden">{t.intro.xpLabel(instrument.xp)}</span>
                </li>
              )}
            </ul>
          </div>
          <div className="play-says">
            <NeoSlot mood="happy" />
            <p className="play-bubble">
              {resuming ? t.intro.resumeText(answeredCount, total) : instrument.intro}
            </p>
          </div>
          <div className="play-actions">
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                setStarted(true);
                // Le temps passé sur l'accueil ne compte pas dans celui de la première question.
                player.markShown();
              }}
            >
              {resuming ? t.intro.resume : t.intro.start}
            </button>
          </div>
          <div className="play-fineprint">
            <p>{t.intro.skip}</p>
            {instrument.source_note && (
              <p>
                <strong>{t.intro.source}</strong> {instrument.source_note}
              </p>
            )}
            {shared === true && <p className="play-fineprint__shared">{t.intro.shared}</p>}
          </div>
        </div>
      </div>
    );
  }

  if (screen === 'chapter' && pendingChapter) {
    return (
      <div className="play play--chapter">
        {topBar}
        {progress}
        {leaveNotice}
        <div className="play-stage">
          <div className="play-hero">
            {chapters.length > 1 && (
              <p className="play-kicker">
                {t.chapter.kicker(chapterPosition + 1, chapters.length)}
              </p>
            )}
            <h1 ref={setFocusTarget} tabIndex={-1}>
              {pendingChapter.title}
            </h1>
          </div>
          <div className="play-says">
            <NeoSlot mood="thinking" />
            <p className="play-bubble">{pendingChapter.intro}</p>
          </div>
          <div className="play-actions">
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                setSeenChapters((seen) => new Set(seen).add(pendingChapter.id));
                player.markShown();
              }}
            >
              {t.chapter.next}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (screen === 'end') {
    const needed = instrument.min_answers ?? Math.ceil(total * 0.6);
    const missing = Math.max(needed - answeredCount, 0);
    return (
      <div className="play play--end">
        {topBar}
        {progress}
        {leaveNotice}
        <div className="play-stage">
          <div className="play-hero">
            <h1 ref={setFocusTarget} tabIndex={-1}>
              {missing > 0 ? t.end.almost : t.end.title}
            </h1>
          </div>
          <div className="play-says">
            <NeoSlot mood="cheer" />
            <p className="play-bubble">{t.end.text(answeredCount, total)}</p>
          </div>
          {missing > 0 && <p className="notice">{t.end.missing(missing)}</p>}
          {player.saveFailed && (
            <p className="notice" role="status">
              {gameFr.question.saveError}
            </p>
          )}
          {player.error && (
            <p className="form-error" role="alert">
              {player.error}
            </p>
          )}
          <div className="play-actions">
            {missing > 0 ? (
              // De question passée en question passée, puis retour ici.
              <button type="button" className="button button--primary" onClick={player.review}>
                {t.end.review}
              </button>
            ) : (
              <button
                type="button"
                className="button button--primary"
                disabled={player.finishing}
                onClick={() => void player.finish()}
              >
                {player.finishing ? t.end.finishing : t.end.finish}
              </button>
            )}
            {index > 0 && (
              <button type="button" className="link-button" onClick={player.back}>
                <span aria-hidden="true">← </span>
                {t.question.previous}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!current) return <Loading />;
  const stored = answers[current.id];
  const answered = stored !== undefined && !stored.skipped;
  const kicker =
    chapterPosition >= 0
      ? t.question.step(chapterPosition + 1, chapters.length, chapters[chapterPosition].title)
      : null;

  return (
    <div className="play play--question">
      {topBar}
      {progress}
      {leaveNotice}
      {player.saveFailed && (
        <p className="notice" role="status">
          {gameFr.question.saveError}
        </p>
      )}
      <div className="play-question">
        {kicker && <p className="play-kicker">{kicker}</p>}
        {/* Une carte neuve par question : ni focus ni survol hérités de la précédente. */}
        <QuestionCard
          key={current.id}
          item={current}
          scale={instrument.scale}
          value={stored?.value}
          onAnswer={player.answer}
          // Une réponse déjà donnée ne se passe pas : « Suivant » avance sans l'effacer.
          onSkip={answered ? undefined : player.skip}
          autoFocus
          describedBy="play-progress-label"
        />
      </div>
      <div className="play-nav">
        {index > 0 && (
          <button type="button" className="link-button" onClick={player.back}>
            <span aria-hidden="true">← </span>
            {t.question.previous}
          </button>
        )}
        {answered && (
          <button type="button" className="link-button play-nav__next" onClick={player.next}>
            {t.question.next}
            <span aria-hidden="true"> →</span>
          </button>
        )}
      </div>
    </div>
  );
}
