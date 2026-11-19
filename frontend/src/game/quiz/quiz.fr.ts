/** Textes du quiz d'arrivée. Les questions elles-mêmes sont dans backend/app/game/content/. */
const plural = (count: number, one: string, many: string) => (count > 1 ? many : one);

export const quizFr = {
  loading: 'Truffe prépare tes questions…',
  leave: 'Revenir plus tard',
  welcome: {
    kicker: 'Quiz d’arrivée',
    title: 'Salut, moi c’est Truffe !',
    intro:
      'Je te raconte une semaine, du réveil jusqu’au week-end, et tu me dis comment tu la vis. À la fin, je te révèle ton archétype.',
    rulesLabel: 'Comment ça marche',
    duration: (minutes: number) => `Environ ${minutes} minutes`,
    rules: [
      { icon: '🙌', text: 'Pas de bonne réponse, juste la tienne' },
      { icon: '⏭️', text: 'Tu peux passer n’importe quelle question' },
      { icon: '⏸️', text: 'Tu t’arrêtes quand tu veux, on reprendra plus tard' },
    ],
    transparency:
      'Tes réponses sont transmises à ta psychologue du Centre des Possibles, comme prévu à ton inscription.',
    start: 'C’est parti !',
    later: 'Plus tard',
  },
  chapter: {
    count: (position: number, total: number) => `Chapitre ${position} sur ${total}`,
    start: 'On y va',
    resumeKicker: 'Te revoilà !',
    resumeText: (answered: number) =>
      `Tu as déjà ${answered} ${plural(answered, 'réponse', 'réponses')}. On reprend là où tu t’étais arrêté·e.`,
    resume: 'On continue',
  },
  question: {
    progress: (position: number, total: number) => `Question ${position} sur ${total}`,
    progressLabel: (position: number, total: number, chapter: string) =>
      `Question ${position} sur ${total}, chapitre ${chapter}`,
    back: 'Retour',
    skip: 'Passer',
    next: 'Suivant',
    later: 'Continuer plus tard',
    pausing: 'Je mets de côté…',
    enough: 'C’est bon, tu as assez de réponses pour découvrir ton archétype.',
    toEnd: 'Voir mon archétype',
    saveError: 'Ta réponse n’est pas encore enregistrée, je réessaie plus tard.',
    pauseError: 'Impossible de mettre en pause pour l’instant. Vérifie ta connexion et réessaie.',
  },
  xp: {
    label: (xp: number) => `${xp} XP gagnés pendant le quiz`,
    announce: (gain: number, total: number) => `+${gain} XP, ${total} XP au total`,
    unit: 'XP',
    gain: (xp: number) => `+${xp}`,
  },
  end: {
    title: 'Tu as fait le tour !',
    text: 'Bravo, tu as fait le tour de ta semaine ! Prêt·e à découvrir ton archétype ?',
    count: (answered: number, total: number) =>
      `${answered} ${plural(answered, 'réponse', 'réponses')} sur ${total} questions.`,
    reveal: 'Révéler mon archétype',
    skipped: (count: number) =>
      `Tu as passé ${count} ${plural(count, 'question', 'questions')}. Tu peux y revenir si tu veux.`,
    review: 'Revoir les questions passées',
    back: 'Revenir à la dernière question',
    missingTitle: 'Encore un petit effort',
    missing: (count: number) =>
      `Il me manque encore ${count} ${plural(count, 'réponse', 'réponses')} pour te révéler ton archétype.`,
    reviewMissing: 'Reprendre les questions passées',
    thinking: 'Truffe rassemble tes réponses…',
  },
  reveal: {
    suspense: 'Roulement de tambour… Je dessine ton badge d’archétype.',
    kicker: 'Ton archétype',
    noArchetypeTitle: 'Ton archétype se dessine encore',
    noArchetype:
      'Je n’ai pas encore assez d’indices pour te trouver un archétype. Les jeux vont m’aider à y voir plus clair.',
    highlightsTitle: 'Ce que j’ai repéré chez toi',
    highlightsHint: 'Sur ta fiche, tu pourras dire « C’est moi » ou « Pas moi » sur chaque curseur.',
    groups: {
      personality: 'Ton caractère',
      interests: 'Ce qui t’attire',
      cognitive: 'Tes points forts',
    } as Record<string, string>,
    between: 'Entre les deux',
    rewardsTitle: 'Tes récompenses',
    bonus: (xp: number) => `+${xp} XP de fin de quiz`,
    total: (xp: number) => `${xp} XP au total`,
    level: (level: number, title: string) => `Niveau ${level} · ${title}`,
    levelUp: 'Niveau supérieur !',
    nextLevel: (missing: number) => `Plus que ${missing} XP avant le niveau suivant`,
    badgesTitle: 'Nouveaux badges',
    sheet: 'Voir ma fiche',
    games: 'Découvrir les jeux',
  },
  done: {
    kicker: 'Quiz d’arrivée terminé',
    intro: 'Tu as déjà fait le quiz d’arrivée. Voici ce qu’il a révélé. Tes curseurs continuent de bouger à chaque jeu.',
    badgesTitle: 'Tes badges',
  },
};
