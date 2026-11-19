import { Link } from 'react-router-dom';
import type { SheetAttribute } from '../types';
import { Glyph, Seal } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr, typo } from './sheet.fr';

const t = sheetFr.attributes;

type Reveal = NonNullable<SheetAttribute['reveal_with']>;

const linkFor = (reveal: Reveal) => (reveal.kind === 'quiz' ? '/jeune/quiz' : '/jeune/jeux');

function RevealHint({ reveal }: { reveal: Reveal | null }) {
  if (!reveal) return <p className="sheet-attr__hint">{t.later}</p>;
  return (
    <Link to={linkFor(reveal)} className="sheet-attr__hint sheet-link">
      {reveal.kind === 'quiz' ? t.finish(reveal.title) : t.play(reveal.title)}
    </Link>
  );
}

/** Une seule invitation quand aucun attribut n'est connu, plutôt que six fois la même. */
function SharedHint({ attributes }: { attributes: SheetAttribute[] }) {
  const targets = new Map<string, Reveal>();
  for (const attribute of attributes) {
    if (attribute.reveal_with) targets.set(attribute.reveal_with.id, attribute.reveal_with);
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
        {only.kind === 'quiz' ? t.finishAll(only.title) : t.playAll(only.title)}
      </Link>
    </p>
  );
}

/** Les six attributs, de 8 à 20, en médaillons. Un attribut inconnu montre comment le révéler. */
export function Attributes({ attributes }: { attributes: SheetAttribute[] }) {
  const noneKnown = attributes.every((attribute) => attribute.score === null);

  return (
    <SheetBox id="sheet-attributes" title={t.title} intro={t.intro} className="sheet-area--attributes">
      {noneKnown && <SharedHint attributes={attributes} />}
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
                <span className="visually-hidden">
                  {known ? ` : ${attribute.score} sur 20` : ` : ${t.unknown}`}
                </span>
              </h4>
              <p className="sheet-attr__description">{typo(attribute.description)}</p>
              {!known && !noneKnown && <RevealHint reveal={attribute.reveal_with ?? null} />}
            </li>
          );
        })}
      </ul>
    </SheetBox>
  );
}
