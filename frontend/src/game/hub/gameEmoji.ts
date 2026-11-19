/**
 * Le contenu nomme ses icônes par un mot (champ `icon` des jeux et des badges).
 * Un mot inconnu affiche un dé : ajouter ici les icônes des nouveaux jeux.
 */
const EMOJI: Record<string, string> = {
  backpack: '🎒',
  blocks: '🧱',
  bolt: '⚡',
  brain: '🧠',
  cards: '🃏',
  chess: '♟️',
  clock: '⏱️',
  color: '🎨',
  colors: '🎨',
  compass: '🧭',
  dice: '🎲',
  digits: '🔢',
  eye: '👀',
  feather: '🪶',
  flag: '🚩',
  flame: '🔥',
  grid: '🔲',
  hammer: '🔨',
  hands: '🤝',
  key: '🔑',
  lightbulb: '💡',
  map: '🗺️',
  maze: '🌀',
  medal: '🏅',
  memory: '🧠',
  mirror: '🪞',
  music: '🎵',
  numbers: '🔢',
  palette: '🎨',
  path: '🧭',
  paw: '🐾',
  pattern: '🔷',
  puzzle: '🧩',
  rocket: '🚀',
  shapes: '🔷',
  sparkles: '✨',
  star: '⭐',
  stars: '🌟',
  target: '🎯',
  timer: '⏱️',
  trophy: '🏆',
};

export function gameEmoji(icon: string | undefined): string {
  return (icon && EMOJI[icon]) || '🎲';
}
