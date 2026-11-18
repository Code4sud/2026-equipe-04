import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { YouthSummary } from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { formatDateTime } from '../../components/format';
import { fr } from '../../content/fr';

const t = fr.backoffice;

export function YouthListPage() {
  const [youths, setYouths] = useState<YouthSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setYouths((await api.listYouths(signal)).youths);
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!youths) return <Loading />;

  return (
    <div className="stack">
      <h1>{t.listTitle}</h1>
      {youths.length === 0 ? (
        <p className="empty">{t.empty}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t.name}</th>
                <th scope="col">{t.lastActivity}</th>
                <th scope="col" className="numeric">{t.validated}</th>
                <th scope="col" className="numeric">{t.pending}</th>
                <th scope="col">{t.sharing}</th>
              </tr>
            </thead>
            <tbody>
              {youths.map((youth) => (
                <tr key={youth.id}>
                  <th scope="row">
                    <Link to={`/psy/jeunes/${youth.id}`}>{youth.display_name}</Link>
                  </th>
                  <td>{youth.last_activity_at ? formatDateTime(youth.last_activity_at) : t.never}</td>
                  <td className="numeric">{youth.validated_skills}</td>
                  <td className="numeric">{youth.pending_skills}</td>
                  <td>
                    <span className={youth.share_transcripts ? 'chip chip--on' : 'chip'}>
                      {youth.share_transcripts ? t.shared : t.notShared}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
