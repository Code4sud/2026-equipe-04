import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import { CognitivePlayer } from '../cognitive/CognitivePlayer';
import type { InstrumentKind } from '../types';
import { QuestionnairePlayer } from './QuestionnairePlayer';

export default function PlayPage() {
  const { instrumentId = '' } = useParams();
  const [kind, setKind] = useState<InstrumentKind | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .status(controller.signal)
      .then((status) => {
        const found = status.instruments.find((entry) => entry.id === instrumentId);
        if (found) setKind(found.kind);
        else setError('Ce jeu n’existe pas.');
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [instrumentId]);

  if (error) return <ErrorState message={error} />;
  if (!kind) return <Loading />;
  return kind === 'performance' ? (
    <CognitivePlayer instrumentId={instrumentId} />
  ) : (
    <QuestionnairePlayer instrumentId={instrumentId} />
  );
}
