import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { Privacy } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { formatDay } from '../../components/format';
import { fr } from '../../content/fr';

const t = fr.me;

export function MePage() {
  const { user, signOut } = useAuth();
  const [privacy, setPrivacy] = useState<Privacy | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setPrivacy(await api.getPrivacy(signal));
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
  if (!privacy) return <Loading />;

  return (
    <div className="scroll-area">
      <div className="page stack">
        <header className="page-head">
          <h1>{user?.display_name ?? t.title}</h1>
          <p className="muted">{t.intro}</p>
        </header>

        <section className="card stack-sm sharing-info">
          <h2>{t.shareTitle}</h2>
          <p className="muted">{t.shareHint(privacy.consent_at ? formatDay(privacy.consent_at) : null)}</p>
        </section>

        <button type="button" className="button" onClick={signOut}>
          {fr.common.logout}
        </button>
      </div>
    </div>
  );
}
