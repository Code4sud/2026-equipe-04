import type { PublicInstrument } from '../types';
import { chapterProgress } from './quizLogic';

/** Barre d'avancement découpée en chapitres : on voit où commence chaque partie de la semaine. */
export function ChapterProgress({
  instrument,
  index,
  label,
}: {
  instrument: PublicInstrument;
  index: number;
  label: string;
}) {
  const total = instrument.items?.length ?? 0;
  return (
    <div
      className="quiz-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={Math.min(index, total)}
      aria-valuetext={label}
    >
      {chapterProgress(instrument, index).map((segment) => (
        <span key={segment.id} className="quiz-progress__segment" title={segment.title}>
          <span style={{ width: `${segment.ratio * 100}%` }} />
        </span>
      ))}
    </div>
  );
}
