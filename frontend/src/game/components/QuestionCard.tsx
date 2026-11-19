import { useEffect, useRef, useState, type FormEvent } from 'react';
import { gameFr } from '../content.fr';
import { NEO_STILLS } from '../neo/NeoAvatar';
import type { AnswerValue, GameItem, ItemOption, LikertScale } from '../types';
import { frenchSpacing } from './frenchSpacing';
import './QuestionCard.css';

const t = gameFr.question;
const FOX = '\u{1F98A}';
/** Au-delà, une option est trop longue pour tenir dans une grille de pastilles. */
const SHORT_LABEL = 24;

interface Props {
  item: GameItem;
  /** Échelle de l'instrument, si la question n'a pas la sienne. */
  scale?: LikertScale;
  value?: AnswerValue;
  onAnswer: (value: AnswerValue) => void;
  onSkip?: () => void;
  /**
   * Place le focus sur l'énoncé à l'affichage, pour que les lecteurs d'écran l'annoncent.
   * Avec une carte par question (`key` = id de la question), c'est à chaque nouvelle question.
   */
  autoFocus?: boolean;
  /** Id d'un texte lu avec l'énoncé quand il prend le focus (avancement, par exemple). */
  describedBy?: string;
}

function scalePoints(scale: LikertScale) {
  return Array.from({ length: scale.max - scale.min + 1 }, (_, index) => {
    const value = scale.min + index;
    return { value, label: scale.labels?.[index] ?? String(value) };
  });
}

/** Beaucoup de choix courts (couleurs, saisons…) : une grille se lit mieux qu'une longue liste. */
function isCompact(options: ItemOption[]) {
  return (
    options.some((option) => option.color) ||
    (options.length >= 5 && options.every((option) => option.label.length <= SHORT_LABEL))
  );
}

function OptionContent({ option }: { option: ItemOption }) {
  return (
    <>
      {option.color ? (
        <span className="question__swatch" style={{ background: option.color }} aria-hidden="true" />
      ) : (
        option.emoji && (
          <span className="question__emoji" aria-hidden="true">
            {/* Le renard de l'app, c'est Truffe : son portrait plutôt que l'emoji. */}
            {option.emoji === FOX ? <img className="question__neo" src={NEO_STILLS.happy} alt="" /> : option.emoji}
          </span>
        )
      )}
      <span className="question__label">{frenchSpacing(option.label)}</span>
    </>
  );
}

/** Affiche n'importe quelle question (Likert, choix, texte libre). Sans logique de partie. */
export function QuestionCard({
  item,
  scale,
  value,
  onAnswer,
  onSkip,
  autoFocus = false,
  describedBy,
}: Props) {
  const multiple = (item.max_choices ?? 1) > 1;
  const [selected, setSelected] = useState<string[]>([]);
  const [text, setText] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const showText = item.type === 'text' || item.allow_text;
  const likert = item.scale ?? scale;
  const compact = item.options ? isCompact(item.options) : false;
  const swatches = item.options?.some((option) => option.color) ?? false;

  useEffect(() => {
    setSelected(Array.isArray(value) ? value : []);
    setText(value && typeof value === 'object' && 'text' in value ? value.text : '');
  }, [item.id, value]);

  useEffect(() => {
    if (autoFocus) heading.current?.focus({ preventScroll: true });
  }, [autoFocus, item.id]);

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
      <h1
        id={`q-${item.id}`}
        ref={heading}
        tabIndex={-1}
        className="question__prompt"
        aria-describedby={describedBy}
      >
        {frenchSpacing(item.prompt)}
      </h1>
      {item.hint && <p className="muted">{frenchSpacing(item.hint)}</p>}

      <div
        className={[
          'question__options',
          compact && 'question__options--grid',
          swatches && 'question__options--swatches',
        ]
          .filter(Boolean)
          .join(' ')}
      >
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
            <OptionContent option={option} />
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
