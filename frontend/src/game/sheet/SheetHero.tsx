import { ArchetypeBadge, ArchetypeQuality } from '../archetype/ArchetypeBadge';
import { isBalancedArchetype } from '../archetype/balanced';
import { frenchSpacing } from '../components/frenchSpacing';
import type { CharacterSheet } from '../types';
import { Seal } from './glyphs';
import { quote, sheetFr, typo } from './sheet.fr';

const t = sheetFr.hero;

/** En-tête de la fiche : badge d'archétype, nom, niveau et expérience. */
export function SheetHero({ sheet }: { sheet: CharacterSheet }) {
  const { display_name: name, archetype } = sheet.identity;
  const { xp, level, level_title: title, level_xp: floor, next_level_xp: next } = sheet.progress;
  const ratio = Math.min(1, Math.max(0, (xp - floor) / Math.max(1, next - floor)));

  return (
    <header className="sheet-hero">
      <div className="sheet-hero__badge">
        <ArchetypeBadge archetype={archetype} />
      </div>

      <div className="sheet-hero__id">
        <p className="sheet-kicker">{t.kicker}</p>
        <h2 id="sheet-name" className="sheet-hero__name">
          {name}
        </h2>
        {archetype ? (
          <>
            <p className="sheet-hero__archetype">
              <span className="sheet-label">{t.archetype}</span> <span>{typo(archetype.name)}</span>{' '}
              <ArchetypeQuality quality={archetype.quality} />
            </p>
            <p className="sheet-hero__motto">{quote(frenchSpacing(typo(archetype.motto)))}</p>
          </>
        ) : (
          <>
            <p className="sheet-hero__archetype">
              <span className="sheet-label">{t.archetype}</span> {t.noArchetype}
            </p>
            <p className="sheet-hero__motto">{t.noArchetypeHint}</p>
          </>
        )}
      </div>

      <div className="sheet-hero__level">
        <div className="sheet-level" aria-hidden="true">
          <Seal className="sheet-seal sheet-level__seal" />
          <span className="sheet-level__label">{t.level}</span>
          <span className="sheet-level__number">{level}</span>
        </div>
        <div className="sheet-level__text">
          <p className="sheet-level__title">
            <span className="visually-hidden">{t.levelFull(level)} : </span>
            {typo(title)}
          </p>
          <div
            className="sheet-xp"
            role="progressbar"
            aria-label={t.xpLabel(level + 1)}
            aria-valuemin={floor}
            aria-valuemax={next}
            aria-valuenow={xp}
            aria-valuetext={t.xpValue(xp, next)}
          >
            <span className="sheet-xp__fill" style={{ width: `${ratio * 100}%` }} />
          </div>
          <p className="sheet-xp__text">
            <span className="sheet-xp__count">{t.xp(xp, next)}</span>
            <span>{t.toNext(next - xp, level + 1)}</span>
          </p>
        </div>
      </div>

      {archetype && (
        <p className="sheet-hero__description">
          {frenchSpacing(typo(archetype.description))}{' '}
          <span className="sheet-hero__note">
            {frenchSpacing(isBalancedArchetype(archetype) ? t.archetypeNoteBalanced : t.archetypeNote)}
          </span>
        </p>
      )}
    </header>
  );
}
