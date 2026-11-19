import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useOutletContext } from 'react-router-dom';
import { api } from '../api/client';
import { ChatIcon, MapIcon, PersonIcon } from '../components/Icons';
import { fr } from '../content/fr';
import { gameFr } from '../game/content.fr';
import '../game/game.css';
import { GamesIcon, SheetIcon } from '../game/icons';

interface YouthContext {
  setPendingTalents: (count: number) => void;
}

export function useYouthContext() {
  return useOutletContext<YouthContext>();
}

export function YouthLayout() {
  const [pendingTalents, setPendingTalents] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    api
      .listSkills(controller.signal)
      .then(({ skills }) => setPendingTalents(skills.filter((s) => s.status === 'pending').length))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  return (
    <div className="shell shell--youth">
      <nav className="tabbar" aria-label={fr.nav.main}>
        <Link to="/jeune/discussion" className="brand tabbar__brand">
          <img src="/flaire-mark.png" alt="" className="brand__mark" width="28" height="28" />
          {fr.appName}
        </Link>
        <NavLink to="/jeune/discussion" className="tabbar__link">
          <ChatIcon />
          {fr.nav.chat}
        </NavLink>
        <NavLink to="/jeune/carte" className="tabbar__link">
          <MapIcon />
          {fr.nav.map}
          {pendingTalents > 0 && (
            <span className="badge">
              <span aria-hidden="true">{pendingTalents}</span>
              <span className="visually-hidden">{fr.nav.pending(pendingTalents)}</span>
            </span>
          )}
        </NavLink>
        <NavLink to="/jeune/jeux" className="tabbar__link">
          <GamesIcon />
          {gameFr.nav.games}
        </NavLink>
        <NavLink to="/jeune/fiche" className="tabbar__link">
          <SheetIcon />
          {gameFr.nav.sheet}
        </NavLink>
        <NavLink to="/jeune/moi" className="tabbar__link">
          <PersonIcon />
          {fr.nav.me}
        </NavLink>
      </nav>
      <main className="shell__main">
        <Outlet context={{ setPendingTalents } satisfies YouthContext} />
      </main>
    </div>
  );
}
