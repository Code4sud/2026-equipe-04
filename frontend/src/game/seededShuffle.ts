/** Graine de 32 bits tirée d'un texte (FNV-1a) : le même texte donne toujours la même graine. */
function seedOf(text: string) {
  let hash = 0x811c9dc5;
  for (let position = 0; position < text.length; position += 1) {
    hash ^= text.charCodeAt(position);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** Générateur pseudo-aléatoire reproductible (mulberry32) : nombres de 0 inclus à 1 exclu. */
function generator(seed: number) {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = Math.imul(state ^ (state >>> 15), state | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Mélange de Fisher-Yates tiré d'une graine : la même graine et la même liste donnent toujours le
 * même ordre, sur n'importe quel appareil. La liste reçue n'est pas modifiée.
 */
export function seededShuffle<T>(list: readonly T[], seed: string): T[] {
  const random = generator(seedOf(seed));
  const shuffled = [...list];
  for (let last = shuffled.length - 1; last > 0; last -= 1) {
    const picked = Math.floor(random() * (last + 1));
    [shuffled[last], shuffled[picked]] = [shuffled[picked], shuffled[last]];
  }
  return shuffled;
}
