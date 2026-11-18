import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { fr } from '../../content/fr';

const t = fr.me;

export function MePage() {
  const { user, signOut } = useAuth();
  const [sharing, setSharing] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setSharing((await api.getPrivacy(signal)).share_transcripts);
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function toggleSharing(value: boolean) {
    setActionError(null);
    setSharing(value);
    try {
      setSharing((await api.updatePrivacy(value)).share_transcripts);
    } catch (caught) {
      setSharing(!value);
      setActionError(errorMessage(caught));
    }
  }

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (sharing === null) return <Loading />;

  return (
    <div className="scroll-area">
      <div className="page stack">
        <header className="page-head">
          <h1>{user?.display_name ?? t.title}</h1>
          <p className="muted">{t.intro}</p>
        </header>

        {actionError && (
          <p className="form-error" role="alert">
            {actionError}
          </p>
        )}

        <label className="toggle card">
          <input
            type="checkbox"
            checked={sharing}
            onChange={(event) => void toggleSharing(event.target.checked)}
          />
          <span>
            <strong>{t.shareTitle}</strong>
            <small className="muted">{t.shareHint}</small>
          </span>
        </label>

        <button type="button" className="button" onClick={signOut}>
          {fr.common.logout}
        </button>
      </div>
    </div>
  );
}
