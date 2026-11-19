import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { api } from '../api/client';
import type { YouthSummary } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { fr } from '../content/fr';
import { SourcesNavLink } from '../game/backoffice/routes';

const t = fr.backoffice;

export function BackofficeLayout() {
  const { user, signOut } = useAuth();
  const [youths, setYouths] = useState<YouthSummary[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    api
      .listYouths(controller.signal)
      .then((result) => setYouths(result.youths))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  return (
    <div className="bo">
      <aside className="bo__side">
        <Link to="/psy/jeunes" className="brand">
          <img src="/flaire-mark.png" alt="" className="brand__mark" width="28" height="28" />
          {fr.appName} · {t.product}
        </Link>
        <nav className="bo__youths" aria-label={t.listTitle}>
          <span className="bo__label">{t.listTitle}</span>
          <ul className="plain-list">
            {youths.map((youth) => (
              <li key={youth.id}>
                <NavLink to={`/psy/jeunes/${youth.id}`} className="bo__youth">
                  <span>{youth.display_name}</span>
                  <small>{youth.validated_skills}</small>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <SourcesNavLink />
        <div className="bo__account">
          <span className="bo__user">{user?.display_name}</span>
          <button type="button" className="link-button" onClick={signOut}>
            {fr.common.logout}
          </button>
        </div>
      </aside>
      <main className="bo__main">
        <div className="page page--wide">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
