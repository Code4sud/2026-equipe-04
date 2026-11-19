import { useCallback, useEffect, useState } from 'react';
import { gameApi } from '../api';
import { NeoSlot } from './NeoSlot';
import { quizFr } from './quiz.fr';
import './quiz.css';
import { QUIZ_ID } from './quizLogic';
import { QuizPlayer } from './QuizPlayer';
import { QuizSummary } from './QuizSummary';

type Mode = 'checking' | 'play' | 'done';

/**
 * Quiz d'arrivée, en plein écran hors de la barre d'onglets.
 * Un quiz déjà terminé montre son résultat ; sinon on reprend à la première question non vue.
 */
export default function QuizPage() {
  const [mode, setMode] = useState<Mode>('checking');
  const showSummary = useCallback(() => setMode('done'), []);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .status(controller.signal)
      .then((status) => {
        const quiz = status.instruments.find((entry) => entry.id === QUIZ_ID);
        setMode(quiz?.state === 'completed' ? 'done' : 'play');
      })
      .catch(() => {
        // Le lecteur affichera l'erreur et proposera de réessayer.
        if (!controller.signal.aborted) setMode('play');
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="quiz">
      {mode === 'checking' && (
        <div className="quiz-screen quiz-screen--center" role="status">
          <NeoSlot mood="thinking" />
          <p>{quizFr.loading}</p>
        </div>
      )}
      {mode === 'play' && <QuizPlayer onAlreadyDone={showSummary} />}
      {mode === 'done' && <QuizSummary />}
    </main>
  );
}
