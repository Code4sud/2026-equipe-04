import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import { NeoAvatar } from '../neo/NeoAvatar';
import { SERIES_SIZE } from '../quiz/quizLogic';
import type { CharacterSheet, GameFact, GameStatus, InstrumentSummary, Verdict } from '../types';
import { Attributes } from './Attributes';
import { Badges } from './Badges';
import { Character } from './Character';
import { DownloadSheet } from './DownloadSheet';
import { ActionIcon, Corner } from './glyphs';
import { Identity, type FactChanges } from './Identity';
import { SheetHero } from './SheetHero';
import { Talents } from './Talents';
import { sheetFr, typo } from './sheet.fr';
import './sheet.css';

const t = sheetFr;

type Quest = 'quiz-start' | 'quiz-resume' | 'games';

const quizOf = (status: GameStatus | null) => status?.instruments.find((instrument) => instrument.kind === 'quiz');

/** Prochaine étape à proposer, d'après l'état des jeux. Sans réponse de l'API, rien. */
function questFor(status: GameStatus | null): Quest | null {
  if (!status) return null;
  const quiz = quizOf(status);
  if (quiz && quiz.completed_count === 0) {
    // Comme sur le hub : une partie ouverte sans aucune réponse n'est pas encore commencée.
    return quiz.state === 'in_progress' && quiz.answered > 0 ? 'quiz-resume' : 'quiz-start';
  }
  const games = status.instruments.filter((instrument) => instrument.kind !== 'quiz');
  if (games.length && games.every((game) => game.completed_count === 0)) return 'games';
  return null;
}

function QuestCard({ quest, quiz }: { quest: Quest; quiz: InstrumentSummary | undefined }) {
  const isQuiz = quest !== 'games';
  const text =
    quest === 'quiz-resume'
      ? t.quest.quizResumeText(SERIES_SIZE)
      : quest === 'quiz-start'
        ? t.quest.quizText(quiz?.total ?? 0, SERIES_SIZE)
        : t.quest.gamesText;
  return (
    <section className="sheet-quest" aria-labelledby="sheet-quest-title">
      <NeoAvatar mood="happy" still className="neo-slot" />
      <div className="sheet-quest__text">
        <p className="sheet-kicker">{t.quest.kicker}</p>
        <h3 id="sheet-quest-title" className="sheet-quest__title">
          {isQuiz ? t.quest.quizTitle : t.quest.gamesTitle}
        </h3>
        {quest === 'quiz-resume' && quiz && (
          <p className="sheet-quest__count">{t.quest.quizProgress(quiz.answered, quiz.total)}</p>
        )}
        <p>{text}</p>
        {/* « Continuer » seul ne dit pas quoi : le lien du quiz renvoie au titre de la quête. */}
        <Link
          to={isQuiz ? '/jeune/quiz' : '/jeune/jeux'}
          className="button button--primary button--small sheet-quest__cta"
          aria-describedby={isQuiz ? 'sheet-quest-title' : undefined}
        >
          {quest === 'quiz-start'
            ? t.quest.quizStart
            : quest === 'quiz-resume'
              ? t.quest.quizResume
              : t.quest.gamesCta}
        </Link>
      </div>
    </section>
  );
}

function patchVerdict(sheet: CharacterSheet, traitId: string, verdict: Verdict | null): CharacterSheet {
  return {
    ...sheet,
    trait_groups: sheet.trait_groups.map((group) => ({
      ...group,
      traits: group.traits.map((trait) => (trait.id === traitId ? { ...trait, verdict } : trait)),
    })),
  };
}

export default function SheetPage() {
  const [sheet, setSheet] = useState<CharacterSheet | null>(null);
  const [status, setStatus] = useState<GameStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      // L'état des jeux sert seulement à proposer la prochaine quête : son échec ne bloque rien.
      const [nextSheet, nextStatus] = await Promise.all([
        gameApi.sheet(signal),
        gameApi.status(signal).catch(() => null),
      ]);
      setStatus(nextStatus);
      setSheet(nextSheet);
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Change le texte même si l'annonce se répète, pour que le lecteur d'écran la relise.
  const announce = useCallback((text: string) => {
    setMessage((current) => (current === text ? `${text} ` : text));
  }, []);

  const changeFact = useCallback(async (key: string, changes: FactChanges): Promise<GameFact> => {
    const { fact } = await gameApi.updateFact(key, changes);
    setSheet((current) =>
      current && { ...current, facts: current.facts.map((item) => (item.key === key ? fact : item)) },
    );
    return fact;
  }, []);

  const changeVerdict = useCallback(
    async (traitId: string, verdict: Verdict | null) => {
      const trait = sheet?.trait_groups.flatMap((group) => group.traits).find((item) => item.id === traitId);
      if (!trait) return;
      const subject =
        trait.kind === 'bipolar'
          ? t.character.pair(typo(trait.low ?? ''), typo(trait.high ?? ''))
          : typo(trait.label ?? '');
      setSheet((current) => current && patchVerdict(current, traitId, verdict));
      try {
        await gameApi.setTraitVerdict(traitId, verdict);
      } catch (caught) {
        setSheet((current) => current && patchVerdict(current, traitId, trait.verdict));
        throw caught;
      }
      announce(
        verdict === 'agree'
          ? t.character.agreed(subject)
          : verdict === 'disagree'
            ? t.character.disagreed(subject)
            : t.character.cleared(subject),
      );
    },
    [sheet, announce],
  );

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!sheet) return <Loading />;

  const quest = questFor(status);
  const completed = status
    ? new Set(status.instruments.filter((instrument) => instrument.completed_count > 0).map((item) => item.id))
    : null;
  // Une image vaut d'être gardée dès qu'il y a un archétype, un détail ou un talent.
  const hasContent =
    Boolean(sheet.identity.archetype) ||
    sheet.facts.some((fact) => !fact.hidden) ||
    sheet.talents.validated.length > 0;
  const quizPending = quest === 'quiz-start' || quest === 'quiz-resume';
  const characterNext = quizPending
    ? { to: '/jeune/quiz', text: t.character.emptyQuiz, cta: t.identity.emptyCta }
    : { to: '/jeune/jeux', text: t.character.empty, cta: t.character.emptyCta };

  return (
    <div className="scroll-area">
      <div className="page page--wide sheet-page">
        <header className="page-head sheet-page__head">
          <h1>{t.title}</h1>
          <p className="muted">{t.intro}</p>
          <p className="sheet-privacy">
            <ActionIcon name="show" />
            {t.transparency}
          </p>
        </header>

        <article className="sheet-paper" aria-labelledby="sheet-name">
          <Corner className="sheet-corner--tl" />
          <Corner className="sheet-corner--tr" />
          <Corner className="sheet-corner--bl" />
          <Corner className="sheet-corner--br" />

          <SheetHero sheet={sheet} />
          {quest && <QuestCard quest={quest} quiz={quizOf(status)} />}

          <div className="sheet-grid">
            <Identity
              facts={sheet.facts}
              quizLink={quizPending || !status ? '/jeune/quiz' : null}
              onChange={changeFact}
              announce={announce}
            />
            <Talents talents={sheet.talents} />
            <Attributes attributes={sheet.attributes} completed={completed} />
            <Character groups={sheet.trait_groups} next={characterNext} onVerdict={changeVerdict} />
            <Badges badges={sheet.progress.badges} />
          </div>
        </article>

        {hasContent && <DownloadSheet sheet={sheet} announce={announce} />}

        <p className="visually-hidden" aria-live="polite">
          {message}
        </p>
      </div>
    </div>
  );
}

