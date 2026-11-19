/** Textes communs du jeu. Chaque écran garde les siens dans son dossier. */
export const gameFr = {
  nav: { games: 'Jeux', sheet: 'Ma fiche' },
  question: {
    skip: 'Passer',
    back: 'Retour',
    confirm: 'Valider',
    other: 'Autre chose…',
    progress: (current: number, total: number) => `${current} sur ${total}`,
    saveError: 'Ta réponse n’est pas encore enregistrée, je réessaie à la fin.',
  },
  run: {
    finish: 'Terminer',
    pause: 'Continuer plus tard',
    notEnough: (count: number) => `Encore un petit effort : il faut au moins ${count} réponses.`,
  },
};
