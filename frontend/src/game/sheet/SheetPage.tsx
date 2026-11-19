import { useEffect, useState } from 'react';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import type { CharacterSheet } from '../types';

/** À remplacer par le lot « fiche perso ». */
export default function SheetPage() {
  const [sheet, setSheet] = useState<CharacterSheet | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .sheet(controller.signal)
      .then(setSheet)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!sheet) return <Loading />;
  return (
    <div className="scroll-area">
      <div className="page stack">
        <h1>{sheet.identity.display_name}</h1>
        <p>{sheet.identity.clan?.name}</p>
      </div>
    </div>
  );
}
