/** Textes du déroulé d’un questionnaire et de son écran de résultat. */
const plural = (count: number, one: string, many: string) => (count > 1 ? many : one);

export const playFr = {
  backToHub: 'Retour aux jeux',
  pause: 'Continuer plus tard',
  pauseError: 'Je n’ai pas pu garder ta place. Vérifie ta connexion et réessaie.',
  intro: {
    start: 'C’est parti',
    resume: 'Reprendre',
    resumeText: (answered: number, total: number) =>
      `Déjà ${answered} ${plural(answered, 'réponse', 'réponses')} sur ${total} ! On reprend là où tu t’es arrêté·e.`,
    duration: (minutes: number) => `≈ ${minutes} min`,
    durationLabel: (minutes: number) => `Environ ${minutes} ${plural(minutes, 'minute', 'minutes')}`,
    questions: (count: number) => `${count} ${plural(count, 'question', 'questions')}`,
    xp: (xp: number) => `+${xp} XP`,
    xpLabel: (xp: number) => `${xp} points d’expérience à gagner`,
    source: 'D’où viennent les questions ?',
    shared: 'La psychologue verra tes réponses.',
    skip: 'Une question ne te parle pas ? Passe-la, sans souci.',
  },
  question: {
    progress: (current: number, total: number) => `Question ${current} sur ${total}`,
    step: (index: number, count: number, title: string) =>
      count > 1 ? `Étape ${index} sur ${count} · ${title}` : title,
    xp: (xp: number) => `+${xp} XP`,
    xpLabel: (xp: number) => `${xp} points gagnés pendant ce jeu`,
    previous: 'Question précédente',
    keep: 'Garder ma réponse',
  },
  chapter: {
    kicker: (index: number, count: number) => `Étape ${index} sur ${count}`,
    next: 'Continuer',
  },
  end: {
    title: 'C’est tout bon !',
    almost: 'Presque fini !',
    text: (answered: number, total: number) =>
      `Tu as répondu à ${answered} ${plural(answered, 'question', 'questions')} sur ${total}.`,
    finish: 'Voir mon résultat',
    finishing: 'Je fais les comptes…',
    missing: (missing: number) =>
      `Encore ${missing} ${plural(missing, 'réponse', 'réponses')} et c’est bon. Tu peux revenir sur les questions passées.`,
    review: 'Revoir les questions passées',
  },
  result: {
    title: 'Bien joué !',
    xpTitle: 'XP gagnés',
    xpSpoken: (xp: number) => `Tu gagnes ${xp} XP.`,
    levelUp: (level: number) => `Niveau ${level} !`,
    levelTitle: (title: string) => `Te voilà ${title}.`,
    badges: (count: number) => (count > 1 ? 'Nouveaux badges' : 'Nouveau badge'),
    highlights: 'Ce qui ressort de tes jeux',
    views: {
      personality: 'Ton caractère',
      interests: 'Ce qui t’attire le plus',
    } as Record<string, string>,
    highlightsHint: 'Tout ce que tu as joué compte. Sur ta fiche, c’est toi qui dis si ça te ressemble.',
    tools: 'Tes quatre outils',
    toolsHint: 'Ce que disent tes jeux jusqu’ici. Sur ta fiche, tu dis « C’est moi » ou « Pas moi ».',
    notYet: 'Pas encore assez de réponses',
    leaning: (low: string, high: string) => `Entre ${low} et ${high}`,
    hub: 'Retour aux jeux',
    sheet: 'Voir ma fiche',
  },
  /** « Ton style » : les quatre curseurs du Big Five qu’il alimente, sous leur nom de jeu. */
  styleTools: [
    { trait: 'extraversion', name: 'Ta batterie', emoji: '🔋' },
    { trait: 'openness', name: 'Ta lunette', emoji: '🔭' },
    { trait: 'agreeableness', name: 'Ta boussole', emoji: '🧭' },
    { trait: 'conscientiousness', name: 'Ton sac à dos', emoji: '🎒' },
  ],
  groups: {
    personality: 'Caractère',
    interests: 'Ce qui t’attire',
    cognitive: 'Point fort',
  } as Record<string, string>,
  locked: {
    title: 'Ce jeu est encore verrouillé',
    text: 'Il se débloque quand tu as terminé le quiz d’arrivée.',
    quiz: 'Faire le quiz',
  },
  notFound: 'Ce jeu n’existe pas, ou plus.',
};
