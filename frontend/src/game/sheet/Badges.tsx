import type { Badge } from '../types';
import { ActionIcon, Glyph, Seal } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr, typo } from './sheet.fr';

const t = sheetFr.badges;
const STAR_ICONS = new Set(['star', 'stars']);

/** Badges gagnés en tête ; les autres restent grisés et disent comment les obtenir. */
export function Badges({ badges }: { badges: Badge[] }) {
  const earned = badges.filter((badge) => badge.earned);
  const ordered = [...earned, ...badges.filter((badge) => !badge.earned)];

  return (
    <SheetBox
      id="sheet-badges"
      title={t.title}
      aside={t.count(earned.length, badges.length)}
      className="sheet-area--badges"
    >
      <ul className="sheet-badges">
        {ordered.map((badge) => {
          const classes = [
            'sheet-badge',
            badge.earned ? 'is-earned' : 'is-goal',
            STAR_ICONS.has(badge.icon) && 'sheet-badge--star',
          ]
            .filter(Boolean)
            .join(' ');
          return (
            <li key={badge.id} className={classes}>
              <span className="sheet-badge__medal" aria-hidden="true">
                <Seal />
                <Glyph name={badge.icon} className="sheet-glyph sheet-badge__icon" />
              </span>
              <span className="sheet-badge__text">
                <span className="sheet-badge__label">{typo(badge.label)}</span>
                <span className="sheet-badge__state">
                  {badge.earned ? (
                    <>
                      <ActionIcon name="check" />
                      {t.earned}
                    </>
                  ) : (
                    t.goal
                  )}
                </span>
                <span className="sheet-badge__description">{typo(badge.description)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </SheetBox>
  );
}
