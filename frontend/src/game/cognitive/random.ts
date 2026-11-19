/** Hasard des jeux : Math.random suffit, rien de secret ne dépend de ces tirages. */

export function randomInt(max: number): number {
  return Math.floor(Math.random() * max);
}

export function pick<T>(items: readonly T[]): T {
  return items[randomInt(items.length)];
}

export function shuffle<T>(items: readonly T[]): T[] {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const other = randomInt(index + 1);
    [copy[index], copy[other]] = [copy[other], copy[index]];
  }
  return copy;
}

export function sample<T>(items: readonly T[], count: number): T[] {
  return shuffle(items).slice(0, count);
}

function hasRun(sequence: number[]): boolean {
  for (let index = 2; index < sequence.length; index += 1) {
    const first = sequence[index - 1] - sequence[index - 2];
    const second = sequence[index] - sequence[index - 1];
    if (first === second && Math.abs(first) === 1) return true;
  }
  return false;
}

/** Série sans répétition ; pour les chiffres, sans suite évidente comme 4, 5, 6. */
export function spanSequence(symbols: number[], length: number, avoidRuns: boolean): number[] {
  const draw = () =>
    length <= symbols.length
      ? sample(symbols, length)
      : Array.from({ length }, () => pick(symbols));
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const sequence = draw();
    if (!avoidRuns || !hasRun(sequence)) return sequence;
  }
  return draw();
}

export interface StroopPair {
  word: string;
  ink: string;
}

/**
 * Paires (mot, encre) équilibrées : chaque encre autant de fois, la part voulue d'essais
 * congruents répartie entre les couleurs, jamais la même encre deux fois de suite.
 * Même règle que le serveur (backend/app/game/performance.py, stroop_sequence).
 */
export function stroopSequence(colors: string[], count: number, congruentRatio: number): StroopPair[] {
  const size = colors.length;
  const inks = [
    ...Array.from({ length: count - (count % size) }, (_, index) => colors[index % size]),
    ...sample(colors, count % size),
  ];
  const slots = shuffle(inks.map((_, index) => index));
  const byInk = new Map(colors.map((color) => [color, slots.filter((slot) => inks[slot] === color)]));
  const target = Math.min(count, Math.round(count * congruentRatio));
  const congruent = new Set<number>();
  const cycle = shuffle(colors);
  while (congruent.size < target) {
    for (const color of cycle) {
      const free = byInk.get(color) ?? [];
      const slot = free.pop();
      if (slot !== undefined && congruent.size < target) congruent.add(slot);
    }
  }
  const turn = new Map(colors.map((color) => [color, randomInt(size - 1)]));
  const pool = inks.map((ink, index) => {
    if (congruent.has(index)) return { word: ink, ink };
    const others = colors.filter((color) => color !== ink);
    const step = turn.get(ink) ?? 0;
    turn.set(ink, step + 1);
    return { word: others[step % others.length], ink };
  });
  for (let attempt = 0; attempt < 500; attempt += 1) {
    const remaining = [...pool];
    const order: StroopPair[] = [];
    while (remaining.length) {
      const last = order.at(-1)?.ink;
      const choices = remaining.flatMap((pair, index) => (pair.ink === last ? [] : [index]));
      if (!choices.length) break;
      order.push(remaining.splice(pick(choices), 1)[0]);
    }
    if (!remaining.length) return order;
  }
  return pool;
}
