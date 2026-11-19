import type { Archetype } from '../types';

/**
 * Identifiant de l'archétype équilibré de archetypes.json (pôle « balanced ») : aucun trait de
 * caractère ne ressort, ses textes ne disent donc pas qu'il en suit un.
 * backend/tests/test_game_archetype.py vérifie qu'il reste celui du contenu.
 */
export const BALANCED_ARCHETYPE_ID = 'cameleon';

export function isBalancedArchetype(archetype: Pick<Archetype, 'id'>): boolean {
  return archetype.id === BALANCED_ARCHETYPE_ID;
}
