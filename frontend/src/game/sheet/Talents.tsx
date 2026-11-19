import { Link } from 'react-router-dom';
import { TalentStar } from '../../components/Icons';
import { fr } from '../../content/fr';
import type { CharacterSheet } from '../types';
import { ActionIcon } from './glyphs';
import { SheetBox } from './SheetBox';
import { quote, sheetFr } from './sheet.fr';

const t = sheetFr.talents;

/** Les talents gardés dans la discussion : le cœur de la fiche, en jaune. */
export function Talents({ talents }: { talents: CharacterSheet['talents'] }) {
  const { validated, pending_count: pending } = talents;

  return (
    <SheetBox
      id="sheet-talents"
      title={t.title}
      icon={<TalentStar />}
      tone="talent"
      className="sheet-area--talents"
      aside={validated.length > 0 ? t.count(validated.length) : undefined}
      intro={validated.length > 0 ? t.intro : undefined}
    >
      {validated.length > 0 ? (
        <ul className="sheet-talents">
          {validated.map((talent) => (
            <li key={talent.id} className="sheet-talent">
              <TalentStar />
              <div className="sheet-talent__text">
                <h4 className="sheet-talent__name">{talent.name}</h4>
                {talent.origin !== 'youth' && (
                  <p className="sheet-talent__category">
                    {fr.map.categories[talent.category] ?? talent.category}
                  </p>
                )}
                {talent.quote && <p className="sheet-talent__quote">{quote(talent.quote)}</p>}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="sheet-empty">
          {t.empty}{' '}
          <Link to="/jeune/discussion" className="sheet-link">
            {t.emptyCta}
          </Link>
        </p>
      )}

      {pending > 0 && (
        <Link to="/jeune/carte" className="sheet-pending">
          <TalentStar />
          <span>{t.pending(pending)}</span>
          <ActionIcon name="arrow" />
        </Link>
      )}
    </SheetBox>
  );
}
