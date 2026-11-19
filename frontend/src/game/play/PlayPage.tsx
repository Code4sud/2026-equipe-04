import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import { CognitivePlayer } from '../cognitive/CognitivePlayer';
import { NeoSlot } from '../hub/NeoSlot';
import type { InstrumentSummary } from '../types';
import { QuestionnairePlayer } from './QuestionnairePlayer';
import { playFr } from './play.fr';
import './play.css';

const t = playFr;
const QUIZ_ID = 'onboarding';
const QUIZ_PATH = '/jeune/quiz';
const HUB_PATH = '/jeune/jeux';

interface Found {
  game: InstrumentSummary;
  shared: boolean | null;
}

function Message({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="play play--message">
      <div className="play-top">
        <Link to={HUB_PATH} className="link-button play-top__leave">
          <span aria-hidden="true">← </span>
          {t.backToHub}
        </Link>
      </div>
      <div className="play-stage">
        <div className="play-hero">
          <NeoSlot mood="thinking" still />
          <h1>{title}</h1>
          {text && <p className="play-hero__tagline">{text}</p>}
        </div>
        {action && <div className="play-actions">{action}</div>}
      </div>
    </div>
  );
}

/** Ouvre un jeu en plein écran et choisit le lecteur selon son type. */
export default function PlayPage() {
  const { instrumentId = '' } = useParams();
  const [found, setFound] = useState<Found | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setError(null);
      setMissing(false);
      setFound(null);
      try {
        const status = await gameApi.status(signal);
        const game = status.instruments.find((entry) => entry.id === instrumentId);
        // Le jeune accepte à l'inscription que la psychologue voie ses réponses : on le rappelle.
        if (game) setFound({ game, shared: true });
        else setMissing(true);
      } catch (caught) {
        if (!signal?.aborted) setError(errorMessage(caught));
      }
    },
    [instrumentId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (missing) return <Message title={t.notFound} />;
  if (!found) return <Loading />;

  const { game, shared } = found;
  // Le quiz d’arrivée a son propre écran (consentement, chapitres, clan).
  if (game.id === QUIZ_ID) return <Navigate to={QUIZ_PATH} replace />;
  if (game.locked) {
    return (
      <Message
        title={t.locked.title}
        text={t.locked.text}
        action={
          <Link to={QUIZ_PATH} className="button button--primary">
            {t.locked.quiz}
          </Link>
        }
      />
    );
  }
  return game.kind === 'performance' ? (
    <CognitivePlayer instrumentId={instrumentId} />
  ) : (
    <QuestionnairePlayer
      key={instrumentId}
      instrumentId={instrumentId}
      shared={shared}
      completedBefore={game.completed_count}
    />
  );
}
