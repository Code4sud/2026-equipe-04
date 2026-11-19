import type { CharacterSheet } from '../types';
import { Crest, Seal } from './glyphs';
import { quote, sheetFr, typo } from './sheet.fr';

const t = sheetFr.hero;

/** En-tête de la fiche : écu du clan, nom, niveau et expérience. */
export function SheetHero({ sheet }: { sheet: CharacterSheet }) {
  const { display_name: name, clan } = sheet.identity;
  const { xp, level, level_title: title, level_xp: floor, next_level_xp: next } = sheet.progress;
  const ratio = Math.min(1, Math.max(0, (xp - floor) / Math.max(1, next - floor)));

  return (
    <header className="sheet-hero">
      <div className="sheet-hero__crest">
        <Crest icon={clan?.icon ?? null} />
      </div>

      <div className="sheet-hero__id">
        <p className="sheet-kicker">{t.kicker}</p>
        <h2 id="sheet-name" className="sheet-hero__name">
          {name}
        </h2>
        {clan ? (
          <>
            <p className="sheet-hero__clan">
              <span className="sheet-label">{t.clan}</span> {typo(clan.name)}
            </p>
            <p className="sheet-hero__motto">{quote(typo(clan.motto))}</p>
          </>
        ) : (
          <>
            <p className="sheet-hero__clan">
              <span className="sheet-label">{t.clan}</span> {t.noClan}
            </p>
            <p className="sheet-hero__motto">{t.noClanHint}</p>
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

      {clan && (
        <p className="sheet-hero__description">
          {typo(clan.description)} <span className="sheet-hero__note">{t.clanNote}</span>
        </p>
      )}
    </header>
  );
}
