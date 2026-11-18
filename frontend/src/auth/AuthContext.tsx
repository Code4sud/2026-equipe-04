import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, configureAuth } from '../api/client';
import type { Role, Session, User } from '../api/types';

const STORAGE_KEY = 'potentiel.session';

interface AuthState {
  user: User | null;
  ready: boolean;
  signIn: (session: Session) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function writeSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Stockage indisponible : la session reste valable jusqu'à la fermeture de la page.
  }
}

export function homePath(role: Role): string {
  return role === 'youth' ? '/jeune/discussion' : '/psy/jeunes';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const stored = readSession();
    configureAuth(stored?.access_token ?? null);
    return stored;
  });
  const [ready, setReady] = useState(session === null);

  const signOut = useCallback(() => {
    writeSession(null);
    configureAuth(null);
    setSession(null);
    setReady(true);
  }, []);

  const signIn = useCallback((next: Session) => {
    writeSession(next);
    configureAuth(next.access_token);
    setSession(next);
    setReady(true);
  }, []);

  useEffect(() => configureAuth(session?.access_token ?? null, signOut), [session, signOut]);

  // Vérifie au démarrage que la session enregistrée est toujours valable.
  const token = session?.access_token;
  useEffect(() => {
    if (!token || ready) return;
    const controller = new AbortController();
    api
      .me(controller.signal)
      .then(() => setReady(true))
      .catch(() => {
        // Hors ligne : on garde la session, une erreur 401 la fermera si besoin.
        if (!controller.signal.aborted) setReady(true);
      });
    return () => controller.abort();
  }, [token, ready]);

  const value = useMemo(
    () => ({ user: session?.user ?? null, ready, signIn, signOut }),
    [session, ready, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider');
  return context;
}
