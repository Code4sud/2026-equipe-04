import type { ReactNode } from 'react';
import { Fleuron } from './glyphs';

interface Props {
  id: string;
  title: string;
  /** Compteur ou précision posés sur le filet, à droite du titre. */
  aside?: ReactNode;
  intro?: ReactNode;
  /** Remplace le fleuron devant le titre. */
  icon?: ReactNode;
  tone?: 'talent';
  className?: string;
  children: ReactNode;
}

/** Case encadrée de la fiche : le titre est posé sur le filet, comme sur une feuille imprimée. */
export function SheetBox({ id, title, aside, intro, icon, tone, className, children }: Props) {
  const classes = ['sheet-box', tone && `sheet-box--${tone}`, className].filter(Boolean).join(' ');
  return (
    <section className={classes} aria-labelledby={`${id}-title`}>
      <header className="sheet-box__head">
        <h3 id={`${id}-title`} className="sheet-box__title">
          {icon ?? <Fleuron />}
          {title}
        </h3>
        <span className="sheet-box__rule" aria-hidden="true" />
        {aside && <span className="sheet-box__aside">{aside}</span>}
      </header>
      <div className="sheet-box__body">
        {intro && <p className="sheet-box__intro">{intro}</p>}
        {children}
      </div>
    </section>
  );
}
