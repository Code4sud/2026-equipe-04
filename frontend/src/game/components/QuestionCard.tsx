import { useEffect, useState, type FormEvent } from 'react';
import { gameFr } from '../content.fr';
import type { AnswerValue, GameItem, LikertScale } from '../types';

const t = gameFr.question;

interface Props {
  item: GameItem;
  /** Échelle de l'instrument, si la question n'a pas la sienne. */
  scale?: LikertScale;
  value?: AnswerValue;
  onAnswer: (value: AnswerValue) => void;
  onSkip?: () => void;
}

function scalePoints(scale: LikertScale) {
  return Array.from({ length: scale.max - scale.min + 1 }, (_, index) => {
    const value = scale.min + index;
    return { value, label: scale.labels?.[index] ?? String(value) };
  });
}

/** Affiche n'importe quelle question (Likert, choix, texte libre). Sans logique de partie. */
export function QuestionCard({ item, scale, value, onAnswer, onSkip }: Props) {
  const multiple = (item.max_choices ?? 1) > 1;
  const [selected, setSelected] = useState<string[]>([]);
  const [text, setText] = useState('');
  const showText = item.type === 'text' || item.allow_text;
  const likert = item.scale ?? scale;

  useEffect(() => {
    setSelected(Array.isArray(value) ? value : []);
    setText(value && typeof value === 'object' && 'text' in value ? value.text : '');
  }, [item.id, value]);

  function toggle(id: string) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((entry) => entry !== id);
      return current.length < (item.max_choices ?? 1) ? [...current, id] : current;
    });
  }

  function submitText(event: FormEvent) {
    event.preventDefault();
    if (text.trim()) onAnswer({ text: text.trim() });
  }

  return (
    <section className="question" aria-labelledby={`q-${item.id}`}>
      <h1 id={`q-${item.id}`} className="question__prompt">
        {item.prompt}
      </h1>
      {item.hint && <p className="muted">{item.hint}</p>}

      <div className="question__options">
        {item.type === 'likert' &&
          likert &&
          scalePoints(likert).map((point) => (
            <button
              key={point.value}
              type="button"
              className="question__option"
              aria-pressed={value === point.value}
              onClick={() => onAnswer(point.value)}
            >
              {point.label}
            </button>
          ))}

        {item.options?.map((option) => (
          <button
            key={option.id}
            type="button"
            className="question__option"
            aria-pressed={multiple ? selected.includes(option.id) : value === option.id}
            onClick={() => (multiple ? toggle(option.id) : onAnswer(option.id))}
          >
            {option.emoji && <span aria-hidden="true">{option.emoji} </span>}
            {option.label}
          </button>
        ))}
      </div>

      {multiple && (
        <button
          type="button"
          className="button button--primary"
          disabled={selected.length === 0}
          onClick={() => onAnswer(selected)}
        >
          {t.confirm}
        </button>
      )}

      {showText && (
        <form className="question__row" onSubmit={submitText}>
          <input
            className="input"
            value={text}
            maxLength={120}
            aria-label={item.placeholder ?? t.other}
            placeholder={item.placeholder ?? t.other}
            onChange={(event) => setText(event.target.value)}
          />
          <button type="submit" className="button button--primary" disabled={!text.trim()}>
            {t.confirm}
          </button>
        </form>
      )}

      {onSkip && (
        <button type="button" className="link-button" onClick={onSkip}>
          {t.skip}
        </button>
      )}
    </section>
  );
}
