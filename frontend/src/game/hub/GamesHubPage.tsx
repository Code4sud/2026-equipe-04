import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import type { GameStatus } from '../types';

/** À remplacer par le lot « jeux questionnaires ». */
export default function GamesHubPage() {
  const [status, setStatus] = useState<GameStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .status(controller.signal)
      .then(setStatus)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!status) return <Loading />;
  return (
    <div className="scroll-area">
      <div className="page stack">
        <h1>Jeux</h1>
        <ul className="stack-sm plain-list">
          {status.instruments.map((game) => (
            <li key={game.id} className="card">
              {game.locked ? game.title : <Link to={`/jeune/jeux/${game.id}`}>{game.title}</Link>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
