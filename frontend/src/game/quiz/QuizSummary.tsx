import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, errorMessage } from '../../components/Feedback';
import { gameApi } from '../api';
import type { CharacterSheet } from '../types';
import { NeoSlot } from './NeoSlot';
import { quizFr } from './quiz.fr';
import { strongestTraits } from './quizLogic';
import { QuizReveal } from './QuizReveal';

/** Quiz déjà terminé : on rappelle l'archétype et les temps forts au lieu d'afficher une erreur. */
export function QuizSummary() {
  const [sheet, setSheet] = useState<CharacterSheet | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((signal?: AbortSignal) => {
    setError(null);
    gameApi
      .sheet(signal)
      .then(setSheet)
      .catch((caught) => {
        if (!signal?.aborted) setError(errorMessage(caught));
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) {
    return (
      <div className="quiz-screen quiz-screen--center">
        <ErrorState message={error} onRetry={() => load()} />
        <Link className="text-link" to="/jeune/discussion">
          {quizFr.leave}
        </Link>
      </div>
    );
  }
  if (!sheet) {
    return (
      <div className="quiz-screen quiz-screen--center" role="status">
        <NeoSlot mood="thinking" />
        <p>{quizFr.loading}</p>
      </div>
    );
  }

  return (
    <QuizReveal
      mode="summary"
      archetype={sheet.identity.archetype}
      highlights={strongestTraits(sheet.trait_groups.flatMap((group) => group.traits))}
      progress={sheet.progress}
      badges={sheet.progress.badges.filter((badge) => badge.earned)}
    />
  );
}
