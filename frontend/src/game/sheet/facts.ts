import type { GameFact } from '../types';

/** La couleur et la passion ouvrent la fiche ; les autres détails gardent l'ordre de l'API. */
const FIRST = [/couleur/, /passion/];

export function orderFacts(facts: GameFact[]) {
  const rank = (fact: GameFact) => {
    const index = FIRST.findIndex((pattern) => pattern.test(fact.key));
    return index < 0 ? FIRST.length : index;
  };
  return facts
    .map((fact, index) => ({ fact, index }))
    .sort((a, b) => rank(a.fact) - rank(b.fact) || a.index - b.index)
    .map(({ fact }) => fact);
}
