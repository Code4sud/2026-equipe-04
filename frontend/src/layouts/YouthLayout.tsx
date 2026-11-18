import { useEffect, useState } from 'react';
import { NavLink, Outlet, useOutletContext } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { fr } from '../content/fr';

interface YouthContext {
  setPendingSkills: (count: number) => void;
}

export function useYouthContext() {
  return useOutletContext<YouthContext>();
}

export function YouthLayout() {
  const { signOut } = useAuth();
  const [pendingSkills, setPendingSkills] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    api
      .listSkills(controller.signal)
      .then(({ skills }) => setPendingSkills(skills.filter((s) => s.status === 'pending').length))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  return (
    <div className="shell shell--youth">
      <header className="topbar">
        <span className="topbar__brand">{fr.appName}</span>
        <button type="button" className="link-button" onClick={signOut}>
          {fr.common.logout}
        </button>
      </header>
      <main className="shell__main">
        <Outlet context={{ setPendingSkills } satisfies YouthContext} />
      </main>
      <nav className="tabbar" aria-label={fr.nav.main}>
        <NavLink to="/jeune/discussion" className="tabbar__link">
          {fr.nav.chat}
        </NavLink>
        <NavLink to="/jeune/competences" className="tabbar__link">
          {fr.nav.skills}
          {pendingSkills > 0 && <span className="badge">{pendingSkills}</span>}
        </NavLink>
      </nav>
    </div>
  );
}
