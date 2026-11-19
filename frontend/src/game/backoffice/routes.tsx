import { lazy, Suspense } from 'react';
import { NavLink } from 'react-router-dom';
import { Loading } from '../../components/Feedback';
import { bo } from './backoffice.fr';
import './nav.css';

const SourcesPage = lazy(() => import('./SourcesPage'));

/** /psy/sources, chargée à la demande comme les autres écrans du jeu. */
export function PsySourcesRoute() {
  return (
    <Suspense fallback={<Loading />}>
      <SourcesPage />
    </Suspense>
  );
}

/** Lien « Sources et méthode » de la barre du backoffice. */
export function SourcesNavLink() {
  return (
    <nav className="bog-nav" aria-label={bo.nav.label}>
      <span className="bo__label">{bo.nav.label}</span>
      <NavLink to="/psy/sources" className="bo__youth">
        {bo.nav.sources}
      </NavLink>
    </nav>
  );
}
