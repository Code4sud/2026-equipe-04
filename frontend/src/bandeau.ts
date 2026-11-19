/*
 * Bandeau commun du Hackathon Azuréen : index.html charge orientation.code4sud.fr/bandeau.js
 * en async, et ce script glisse #c4s-bandeau en tête de <body>, collé en haut de l'écran.
 * Sa hauteur réelle passe sur <html> (--bandeau-h, data-bandeau) pour que l'app se cale dessous,
 * et la suit quand elle change (deux lignes sur un petit écran, rotation).
 * S'il ne vient jamais (hors ligne, bloqué), rien ne change.
 */
const BANDEAU_ID = 'c4s-bandeau';

function follow(bandeau: Element) {
  const root = document.documentElement;
  // Bordure comprise : la marge de la barre d'état peut changer sans toucher au contenu.
  new ResizeObserver(([entry]) => {
    const height = entry.borderBoxSize?.[0]?.blockSize ?? bandeau.getBoundingClientRect().height;
    if (height > 0) {
      root.style.setProperty('--bandeau-h', `${height}px`);
      root.dataset.bandeau = '';
    } else {
      // Retiré ou masqué : l'app reprend tout l'écran.
      root.style.removeProperty('--bandeau-h');
      delete root.dataset.bandeau;
    }
  }).observe(bandeau, { box: 'border-box' });
}

/** Suit le bandeau s'il est déjà là, sinon dès qu'il arrive. */
export function followBandeau() {
  const bandeau = document.getElementById(BANDEAU_ID);
  if (bandeau) {
    follow(bandeau);
    return;
  }
  const watcher = new MutationObserver(() => {
    const inserted = document.getElementById(BANDEAU_ID);
    if (!inserted) return;
    watcher.disconnect();
    follow(inserted);
  });
  watcher.observe(document.body, { childList: true });
}
