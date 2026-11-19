import { useState } from 'react';
import { fr } from '../content/fr';
import { MoonIcon, SunIcon } from './Icons';

type Theme = 'light' | 'dark';

// Le script en tête de index.html relit cette clé pour éviter un flash au chargement.
const STORAGE_KEY = 'potentiel.theme';

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  const background = getComputedStyle(root).getPropertyValue('--color-bg').trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', background);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Stockage indisponible : le choix vaut jusqu'à la fermeture de la page.
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  );
  const next: Theme = theme === 'dark' ? 'light' : 'dark';

  function toggle() {
    applyTheme(next);
    setTheme(next);
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={fr.theme[next]}
      title={fr.theme[next]}
      onClick={toggle}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
