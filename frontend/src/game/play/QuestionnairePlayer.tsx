import { Link } from 'react-router-dom';
import { ErrorState, Loading } from '../../components/Feedback';
import { QuestionCard } from '../components/QuestionCard';
import { gameFr } from '../content.fr';
import { useRunPlayer } from '../useRunPlayer';

const t = gameFr;

/** Déroulé minimal d'un questionnaire. Le lot « jeux questionnaires » l'habille. */
export function QuestionnairePlayer({ instrumentId }: { instrumentId: string }) {
  const player = useRunPlayer(instrumentId);
  const { instrument, items, index, current, answers, result } = player;

  if (player.error && !instrument) return <ErrorState message={player.error} onRetry={player.reload} />;
  if (!instrument) return <Loading />;

  if (result) {
    return (
      <div className="game-screen">
        <h1>{instrument.title}</h1>
        <p>+{result.xp_gained} XP</p>
        <Link className="button button--primary" to="/jeune/jeux">
          {t.nav.games}
        </Link>
      </div>
    );
  }

  return (
    <div className="game-screen">
      <div className="game-progress" aria-hidden="true">
        <span style={{ width: `${(index / Math.max(items.length, 1)) * 100}%` }} />
      </div>
      <p className="muted">{t.question.progress(Math.min(index + 1, items.length), items.length)}</p>
      {player.error && <ErrorState message={player.error} />}
      {player.saveFailed && <p className="notice">{t.question.saveError}</p>}
      {current ? (
        <QuestionCard
          item={current}
          scale={instrument.scale}
          value={answers[current.id]?.value}
          onAnswer={player.answer}
          onSkip={player.skip}
        />
      ) : (
        <button
          type="button"
          className="button button--primary"
          disabled={player.finishing}
          onClick={() => void player.finish()}
        >
          {t.run.finish}
        </button>
      )}
      {index > 0 && (
        <button type="button" className="link-button" onClick={player.back}>
          {t.question.back}
        </button>
      )}
    </div>
  );
}
