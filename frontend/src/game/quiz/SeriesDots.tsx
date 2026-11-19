import { SERIES_SIZE, type SeriesSpot } from './quizLogic';

/**
 * Un point par question de la série : plein pour une question vue, allongé pour celle affichée.
 * Décoratif : le texte qui l'accompagne (« Question 4 sur 10 ») dit la même chose.
 */
export function SeriesDots({ done, position }: SeriesSpot) {
  return (
    <div className="quiz-series" aria-hidden="true">
      {Array.from({ length: SERIES_SIZE }, (_, dot) => (
        <span
          key={dot}
          className={[dot < done && 'is-done', dot === position && 'is-current'].filter(Boolean).join(' ')}
        />
      ))}
    </div>
  );
}
