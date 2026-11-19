import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { errorMessage } from '../components/Feedback';
import { fr } from '../content/fr';

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { signIn } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [acceptSharing, setAcceptSharing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const registering = mode === 'register';

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signIn(
        registering
          ? await api.register(displayName, email, password, acceptSharing)
          : await api.login(email, password),
      );
    } catch (caught) {
      setError(errorMessage(caught));
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <form className="auth__card" onSubmit={submit}>
        <Link to="/bienvenue" className="brand">
          <img src="/flaire-mark.png" alt="" className="brand__mark" width="28" height="28" />
          {fr.appName}
        </Link>
        <h1>{registering ? fr.auth.registerTitle : fr.auth.loginTitle}</h1>
        {registering && <p className="muted">{fr.auth.registerIntro}</p>}

        {registering && (
          <label className="field">
            <span>{fr.auth.displayName}</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="nickname"
              maxLength={80}
              required
            />
          </label>
        )}
        <label className="field">
          <span>{fr.auth.email}</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            inputMode="email"
            required
          />
        </label>
        <label className="field">
          <span>{fr.auth.password}</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={registering ? 'new-password' : 'current-password'}
            minLength={registering ? 8 : undefined}
            required
          />
          {registering && <small className="muted">{fr.auth.passwordHint}</small>}
        </label>

        {registering && (
          <label className="toggle">
            <input
              type="checkbox"
              checked={acceptSharing}
              onChange={(event) => setAcceptSharing(event.target.checked)}
              required
            />
            <span>
              <strong>{fr.auth.shareTitle}</strong>
              <small className="muted">{fr.auth.shareHint}</small>
            </span>
          </label>
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button button--primary" disabled={busy}>
          {registering ? fr.auth.register : fr.auth.login}
        </button>
        <Link className="text-link" to={registering ? '/connexion' : '/inscription'}>
          {registering ? fr.auth.toLogin : fr.auth.toRegister}
        </Link>
      </form>
    </main>
  );
}
