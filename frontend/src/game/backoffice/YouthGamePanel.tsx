import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import type { GameEvent, PsyCursor, PsyOverview, PsyRun } from '../types';
import { bo } from './backoffice.fr';
import './backoffice.css';
import { CursorSection } from './CursorSection';
import { MethodContext, useServerMethod } from './method';
import { RunSection } from './RunSection';
import { Summary, type FactView } from './Summary';
import { useDetails } from './useDetails';
import { YouthReactions } from './YouthReactions';

const t = bo.panel;

/** Résultats du quiz et des jeux dans la fiche d'un jeune, en bas de /psy/jeunes/:id. */
export default function YouthGamePanel({ youthId }: { youthId: string }) {
  // Une clé par jeune : rien ne reste en cache d'une fiche à l'autre.
  return <Panel key={youthId} youthId={youthId} />;
}

function Panel({ youthId }: { youthId: string }) {
  const [overview, setOverview] = useState<PsyOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [printing, setPrinting] = useState<'idle' | 'preparing' | 'ready'>('idle');
  const [incomplete, setIncomplete] = useState(false);
  const method = useServerMethod();

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setError(null);
      try {
        setOverview(await gameApi.psyOverview(youthId, signal));
      } catch (caught) {
        if (!signal?.aborted) setError(errorMessage(caught));
      }
    },
    [youthId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const traits = useDetails(
    useCallback((id: string, signal: AbortSignal) => gameApi.psyTrait(youthId, id, signal), [youthId]),
  );
  const runDetails = useDetails(
    useCallback((id: string, signal: AbortSignal) => gameApi.psyRun(youthId, id, signal), [youthId]),
  );

  // Champs facultatifs tant que l'ancienne version de l'API (avec partage) peut répondre.
  const groups = useMemo(() => overview?.cursor_groups ?? [], [overview]);
  const runs: PsyRun[] = useMemo(() => overview?.runs ?? [], [overview]);
  const facts: FactView[] = overview?.facts ?? [];
  const events: GameEvent[] = overview?.events ?? [];
  const cursors: PsyCursor[] = useMemo(() => groups.flatMap((group) => group.cursors), [groups]);
  const cursorsById = useMemo(() => new Map(cursors.map((cursor) => [cursor.id, cursor])), [cursors]);
  const runsById = useMemo(() => new Map(runs.map((run) => [run.id, run])), [runs]);
  const hasData = runs.length > 0 || cursors.some((cursor) => cursor.n > 0);

  useEffect(() => {
    if (printing !== 'ready') return;
    window.print();
    setPrinting('idle');
  }, [printing]);

  async function printWithDetails() {
    setPrinting('preparing');
    setIncomplete(false);
    const results = await Promise.all([
      ...cursors.filter((cursor) => cursor.n > 0).map((cursor) => traits.load(cursor.id)),
      ...runs.map((run) => runDetails.load(run.id)),
    ]);
    setIncomplete(results.includes(false));
    setPrinting('ready');
  }

  return (
    <section className="bog" aria-labelledby="bog-title">
      <header className="bog__head">
        <div className="bog__title">
          <h2 id="bog-title">{t.title}</h2>
          <p className="muted">{t.intro}</p>
          <p className="bog__caution">{t.caution}</p>
        </div>
        <div className="bog__actions">
          <Link to="/psy/sources" className="bog-link">
            {t.sources}
          </Link>
          {hasData && (
            <button
              type="button"
              className="button button--small"
              onClick={() => void printWithDetails()}
              disabled={printing !== 'idle'}
            >
              {t.print}
            </button>
          )}
        </div>
      </header>
      {printing === 'preparing' && (
        <p className="notice" role="status">
          {t.preparing}
        </p>
      )}
      {incomplete && (
        <p className="notice" role="alert">
          {t.printIncomplete}
        </p>
      )}

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : !overview ? (
        <Loading />
      ) : !hasData ? (
        <p className="empty">{t.empty}</p>
      ) : (
        <MethodContext value={method}>
          <YouthReactions cursors={cursors} facts={facts} events={events} runs={runsById} />
          <Summary
            archetype={overview.archetype}
            progress={overview.progress}
            runs={runs}
            cursors={cursors}
            facts={facts}
          />
          <CursorSection groups={groups} traits={traits} runs={runsById} />
          <RunSection runs={runs} details={runDetails} cursors={cursorsById} />
        </MethodContext>
      )}
    </section>
  );
}
