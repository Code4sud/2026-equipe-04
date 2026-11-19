import { Link } from 'react-router-dom';
import type { SheetAttribute } from '../types';
import { Glyph, Seal } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr, typo } from './sheet.fr';

const t = sheetFr.attributes;

type Reveal = NonNullable<SheetAttribute['reveal_with']>;
/** Jeux déjà terminés par le jeune ; null tant que l'état des jeux n'est pas connu. */
type Completed = ReadonlySet<string> | null;

const linkFor = (reveal: Reveal) => (reveal.kind === 'quiz' ? '/jeune/quiz' : '/jeune/jeux');

/**
 * Jeu à proposer pour révéler un attribut. Le serveur peut proposer un jeu déjà terminé, à
 * rejouer : on ne pousse pas à refaire la même partie pour « débloquer » un attribut, et on
 * renvoie plutôt vers les prochains jeux et talents.
 */
function playable(reveal: Reveal | null | undefined, completed: Completed): Reveal | null {
  if (!reveal || completed?.has(reveal.id)) return null;
  return reveal;
}

function RevealHint({ reveal }: { reveal: Reveal | null }) {
  if (!reveal) return <p className="sheet-attr__hint">{t.later}</p>;
  return (
    <Link to={linkFor(reveal)} className="sheet-attr__hint sheet-link">
      {reveal.kind === 'quiz' ? t.finish(typo(reveal.title)) : t.play(typo(reveal.title))}
    </Link>
  );
}

/** Une seule invitation quand aucun attribut n'est connu, plutôt que six fois la même. */
function SharedHint({ attributes, completed }: { attributes: SheetAttribute[]; completed: Completed }) {
  const targets = new Map<string, Reveal>();
  for (const attribute of attributes) {
    const reveal = playable(attribute.reveal_with, completed);
    if (reveal) targets.set(reveal.id, reveal);
  }
  const [only] = targets.size === 1 ? [...targets.values()] : [];
  if (!only) {
    return (
      <p className="sheet-box__intro">
        {t.laterAll}{' '}
        <Link to="/jeune/jeux" className="sheet-link">
          {t.laterAllCta}
        </Link>
      </p>
    );
  }
  return (
    <p className="sheet-box__intro">
      <Link to={linkFor(only)} className="sheet-link">
        {only.kind === 'quiz' ? t.finishAll(typo(only.title)) : t.playAll(typo(only.title))}
      </Link>
    </p>
  );
}

/**
 * Les six attributs, de 10 à 20, en médaillons, calculés sur les seuls points forts. Un attribut
 * encore caché (score null) montre comment le révéler.
 */
export function Attributes({
  attributes,
  completed = null,
}: {
  attributes: SheetAttribute[];
  completed?: Completed;
}) {
  const noneKnown = attributes.every((attribute) => attribute.score === null);

  return (
    <SheetBox id="sheet-attributes" title={t.title} intro={t.intro} className="sheet-area--attributes">
      {noneKnown && <SharedHint attributes={attributes} completed={completed} />}
      <ul className="sheet-attributes">
        {attributes.map((attribute) => {
          const known = attribute.score !== null;
          return (
            <li key={attribute.id} className={`sheet-attr${known ? '' : ' is-unknown'}`}>
              <div className="sheet-attr__medal" aria-hidden="true">
                <Seal />
                <Glyph name={attribute.icon} className="sheet-glyph sheet-attr__icon" />
                <span className="sheet-attr__score">{known ? attribute.score : '?'}</span>
              </div>
              <h4 className="sheet-attr__label">
                {typo(attribute.label)}
                <span className="visually-hidden">{t.spokenScore(attribute.score)}</span>
              </h4>
              <p className="sheet-attr__description">{typo(attribute.description)}</p>
              {!known && !noneKnown && <RevealHint reveal={playable(attribute.reveal_with, completed)} />}
            </li>
          );
        })}
      </ul>
    </SheetBox>
  );
}
