/** Textes du quiz d'arrivée. Les questions elles-mêmes sont dans backend/app/game/content/. */
const plural = (count: number, one: string, many: string) => (count > 1 ? many : one);

export const quizFr = {
  loading: 'Truffe prépare tes questions…',
  leave: 'Revenir plus tard',
  welcome: {
    kicker: 'Quiz d’arrivée',
    title: 'Salut, moi c’est Truffe !',
    intro:
      'Je te pose 50 questions sur ton quotidien, dix par dix. Pas de bonne réponse, juste la tienne ! À la fin, je te révèle ton archétype.',
    rulesLabel: 'Comment ça marche',
    series: (size: number) => `Des séries de ${size} questions, tirées au hasard`,
    /** `count` : questions vues (passées comprises) qui débloquent les mini-jeux ; `size` : une série. */
    unlock: (count: number, size: number) =>
      count <= size
        ? 'Dès la première série, tu débloques les mini-jeux'
        : `Après ${count} questions, tu débloques les mini-jeux`,
    duration: (minutes: number) => `Environ ${minutes} ${plural(minutes, 'minute', 'minutes')} par série`,
    // Question passée et pause partagent une règle : la liste reste courte avec celle des mini-jeux.
    rules: [{ icon: '⏭️', text: 'Tu peux passer une question ou faire une pause après chaque série' }],
    transparency:
      'Tes réponses sont transmises à ta psychologue du Centre des Possibles, comme prévu à ton inscription.',
    start: 'C’est parti !',
    later: 'Plus tard',
  },
  resume: {
    kicker: 'Quiz d’arrivée',
    title: 'Te revoilà !',
    /**
     * `unseen` : questions encore jamais vues ; `toReveal` : questions à faire avant la révélation,
     * les jamais vues ou plus s'il manque des réponses ; `size` : questions d'une série ;
     * `toUnlock` : questions à voir avant de débloquer les mini-jeux, 0 s'ils le sont.
     */
    text: (answered: number, total: number, unseen: number, toReveal: number, size: number, toUnlock: number) =>
      (answered > 0 ? `Tu as déjà ${answered} ${plural(answered, 'réponse', 'réponses')} sur ${total}. ` : '') +
      (toUnlock > 0
        ? `Encore ${toUnlock} ${plural(toUnlock, 'question', 'questions')} et tu débloques les mini-jeux. `
        : '') +
      (unseen > size
        ? `Je te pose une nouvelle série de ${size} questions.`
        : toReveal > 1
          ? `Plus que ${toReveal} questions avant de découvrir ton archétype !`
          : 'Plus qu’une question avant de découvrir ton archétype !'),
    start: 'C’est reparti !',
  },
  question: {
    series: (position: number, size: number) => `Question ${position} sur ${size}`,
    answered: (answered: number, total: number) =>
      `${answered} ${plural(answered, 'réponse', 'réponses')} sur ${total}`,
    reviewing: 'Questions passées',
    /** Question d'une séance précédente, revue avec « Retour ». */
    earlier: (skipped: boolean) => (skipped ? 'Tu l’avais passée' : 'Tu y as déjà répondu'),
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
  series: {
    title: 'Série terminée !',
    text: 'Bien joué ! Tu enchaînes ou tu fais une pause ? C’est toi qui vois.',
    /** `toReveal` : questions à faire avant la révélation, les jamais vues ou plus s'il manque des réponses. */
    left: (toReveal: number) =>
      `Encore ${toReveal} ${plural(toReveal, 'question', 'questions')} avant de découvrir ton archétype`,
    /** `next` : questions de la série suivante ; `last` : ce sont les dernières du quiz. */
    more: (next: number, last: boolean) =>
      !last ? `${next} de plus !` : next > 1 ? `Les ${next} dernières !` : 'La dernière !',
    later: 'Je reprends plus tard',
    /** Série qui vient de débloquer les mini-jeux : `next` et `last` comme pour `more`. */
    unlockedText: (next: number, last: boolean) =>
      `Bravo, tu viens de débloquer les mini-jeux ! Tu enchaînes avec ${
        !last ? `${next} questions de plus` : next > 1 ? `les ${next} dernières questions` : 'la dernière question'
      }, ou tu vas jouer ?`,
    unlocked: 'Mini-jeux débloqués',
    toGames: 'Aller aux mini-jeux',
  },
  xp: {
    label: (xp: number) => `${xp} XP gagnés pendant le quiz`,
    announce: (gain: number, total: number) => `+${gain} XP, ${total} XP au total`,
    unit: 'XP',
    gain: (xp: number) => `+${xp}`,
  },
  end: {
    title: 'Tu as fait le tour !',
    text: 'Bravo, tu as fait le tour des questions ! Prêt·e à découvrir ton archétype ?',
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
