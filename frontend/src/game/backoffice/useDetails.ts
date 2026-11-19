import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../../components/Feedback';

export type Detail<T> =
  | { state: 'loading' }
  | { state: 'error'; message: string }
  | { state: 'ready'; data: T };

export interface Details<T> {
  details: Record<string, Detail<T> | undefined>;
  /** Charge un détail une seule fois ; résout à false en cas d'échec. */
  load: (id: string) => Promise<boolean>;
}

/**
 * Détails chargés à la demande (un curseur, une partie) et gardés ensuite :
 * l'impression peut ainsi tout déplier sans recharger.
 */
export function useDetails<T>(fetcher: (id: string, signal: AbortSignal) => Promise<T>): Details<T> {
  const [details, setDetails] = useState<Record<string, Detail<T> | undefined>>({});
  const requests = useRef(new Map<string, Promise<boolean>>());
  const controller = useRef(new AbortController());

  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    const pending = requests.current;
    return () => {
      current.abort();
      pending.clear();
    };
  }, []);

  const load = useCallback(
    (id: string) => {
      const known = requests.current.get(id);
      if (known) return known;
      const { signal } = controller.current;
      setDetails((all) => ({ ...all, [id]: { state: 'loading' } }));
      const request = fetcher(id, signal).then(
        (data) => {
          setDetails((all) => ({ ...all, [id]: { state: 'ready', data } }));
          return true;
        },
        (caught: unknown) => {
          requests.current.delete(id);
          if (!signal.aborted) {
            setDetails((all) => ({ ...all, [id]: { state: 'error', message: errorMessage(caught) } }));
          }
          return false;
        },
      );
      requests.current.set(id, request);
      return request;
    },
    [fetcher],
  );

  return { details, load };
}
