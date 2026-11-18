import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { fr } from '../content/fr';

export function BackofficeLayout() {
  const { user, signOut } = useAuth();
  return (
    <div className="shell shell--backoffice">
      <header className="topbar">
        <span className="topbar__brand">
          {fr.appName} <span className="muted">· {fr.backoffice.title}</span>
        </span>
        <nav className="topbar__nav" aria-label={fr.nav.main}>
          <NavLink to="/psy/jeunes" className="topbar__link">
            {fr.nav.youths}
          </NavLink>
        </nav>
        <span className="topbar__user muted">{user?.display_name}</span>
        <button type="button" className="link-button" onClick={signOut}>
          {fr.common.logout}
        </button>
      </header>
      <main className="shell__main shell__main--scroll">
        <div className="page page--wide">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
