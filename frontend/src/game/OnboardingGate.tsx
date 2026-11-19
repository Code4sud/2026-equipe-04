import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { Loading } from '../components/Feedback';
import { gameApi } from './api';

/** Envoie sur le quiz à la première connexion. Une panne de l'API ne bloque jamais l'app. */
export function OnboardingGate() {
  const [mustOnboard, setMustOnboard] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .status(controller.signal)
      .then((status) => setMustOnboard(status.must_onboard))
      .catch(() => {
        if (!controller.signal.aborted) setMustOnboard(false);
      });
    return () => controller.abort();
  }, []);

  if (mustOnboard === null) return <Loading />;
  return mustOnboard ? <Navigate to="/jeune/quiz" replace /> : <Outlet />;
}
