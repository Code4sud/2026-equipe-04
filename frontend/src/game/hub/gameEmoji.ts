/**
 * Le contenu nomme ses icônes par un mot (champ `icon` des jeux et des badges, voir
 * backend/app/game/content/instruments/*.json et sheet.json).
 * Un mot inconnu affiche un dé : ajouter ici les icônes des nouveaux jeux.
 */
const EMOJI: Record<string, string> = {
  backpack: '🎒',
  blocks: '🧱',
  bolt: '⚡',
  brain: '🧠',
  cards: '🃏',
  chess: '♟️',
  chest: '💎',
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
  hourglass: '⏳',
  key: '🔑',
  lantern: '🏮',
  lightbulb: '💡',
  lock: '🔒',
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
  sail: '⛵',
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
