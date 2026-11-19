import type { Archetype } from '../types';
import './archetype.css';

export type ArchetypeBadgeSize = 'small' | 'medium' | 'large';

interface Props {
  /** Null tant que l'archétype n'est pas révélé : le médaillon montre « ? ». */
  archetype: Pick<Archetype, 'name' | 'emoji' | 'quality'> | null;
  /** `large` : révélation du quiz ; `medium` : fiche et fin de partie ; `small` : backoffice. */
  size?: ArchetypeBadgeSize;
  /** Nom et qualité écrits sous le médaillon. */
  caption?: boolean;
  className?: string;
}

/**
 * Badge rond de l'archétype : médaillon crème cerclé d'un double anneau abricot, l'emoji au
 * centre. Le médaillon est décoratif : le nom est toujours écrit à côté ou dessous.
 * exportPng.ts (drawArchetypeBadge) le redessine avec les mêmes proportions.
 */
export function ArchetypeBadge({ archetype, size = 'medium', caption = false, className = '' }: Props) {
  const classes = ['archetype-badge', `archetype-badge--${size}`, !archetype && 'archetype-badge--unknown', className]
    .filter(Boolean)
    .join(' ');
  return (
    <span className={classes}>
      <span className="archetype-badge__medal" aria-hidden="true">
        <span className="archetype-badge__emoji">{archetype?.emoji ?? '?'}</span>
      </span>
      {caption && archetype && (
        <span className="archetype-badge__caption">
          <strong className="archetype-badge__name">{archetype.name}</strong>
          <ArchetypeQuality quality={archetype.quality} />
        </span>
      )}
    </span>
  );
}

/** Pastille de la qualité de l'archétype (« Sociable », « Entre les deux »). */
export function ArchetypeQuality({ quality }: { quality: string }) {
  return <span className="archetype-quality">{quality}</span>;
}
