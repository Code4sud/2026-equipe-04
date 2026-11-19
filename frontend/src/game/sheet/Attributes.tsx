import { Link } from 'react-router-dom';
import type { SheetAttribute } from '../types';
import { Glyph, Seal } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr, typo } from './sheet.fr';

const t = sheetFr.attributes;

function RevealHint({ reveal }: { reveal: SheetAttribute['reveal_with'] }) {
  if (!reveal) return <p className="sheet-attr__hint">{t.later}</p>;
  const isQuiz = reveal.kind === 'quiz';
  return (
    <Link to={isQuiz ? '/jeune/quiz' : '/jeune/jeux'} className="sheet-attr__hint sheet-link">
      {isQuiz ? t.finish(reveal.title) : t.play(reveal.title)}
    </Link>
  );
}

/** Les six attributs, de 8 à 20, en médaillons. Un attribut inconnu montre comment le révéler. */
export function Attributes({ attributes }: { attributes: SheetAttribute[] }) {
  return (
    <SheetBox id="sheet-attributes" title={t.title} intro={t.intro} className="sheet-area--attributes">
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
              {!known && <RevealHint reveal={attribute.reveal_with ?? null} />}
            </li>
          );
        })}
      </ul>
    </SheetBox>
  );
}
