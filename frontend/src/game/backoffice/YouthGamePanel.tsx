import { useEffect, useState } from 'react';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import type { PsyOverview } from '../types';

/** À remplacer par le lot « backoffice psy ». */
export default function YouthGamePanel({ youthId }: { youthId: string }) {
  const [overview, setOverview] = useState<PsyOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setOverview(null);
    gameApi
      .psyOverview(youthId, controller.signal)
      .then(setOverview)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [youthId]);

  if (error) return <ErrorState message={error} />;
  if (!overview) return <Loading />;
  return (
    <section className="stack-sm">
      <h2>Quiz et jeux</h2>
      {!overview.shared && <p className="notice">Résultats non partagés.</p>}
    </section>
  );
}
