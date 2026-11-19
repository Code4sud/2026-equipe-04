/** Textes du hub des jeux. */
const plural = (count: number, one: string, many: string) => (count > 1 ? many : one);

export const hubFr = {
  title: 'Tes jeux',
  intro: 'Chaque partie t’apporte de l’XP et précise ta fiche. Rien à réviser : réponds comme tu es.',
  shared: 'La psychologue voit tes parties et tes réponses.',
  level: (level: number) => `Niveau ${level}`,
  xpLabel: 'Progression vers le niveau suivant',
  xpCount: (xp: number, next: number) => `${xp} / ${next} XP`,
  xpMissing: (missing: number, level: number) => `encore ${missing} XP pour le niveau ${level}`,
  xpValue: (xp: number, next: number, level: number) =>
    `${xp} XP sur ${next}, niveau ${level} en cours`,
  quiz: {
    title: 'Ton quiz d’arrivée t’attend',
    progress: (answered: number, total: number) =>
      `${answered} sur ${total} ${plural(total, 'question', 'questions')}`,
    hint: 'Termine-le pour débloquer tous les jeux.',
    resume: 'Reprendre le quiz',
    start: 'Faire le quiz',
    progressLabel: 'Avancée du quiz',
  },
  games: 'Les jeux',
  empty: 'Pas encore de jeu ici. Reviens bientôt !',
  card: {
    new: 'Nouveau',
    inProgress: 'En cours',
    progress: (answered: number, total: number) => `${answered} sur ${total}`,
    done: 'Terminé',
    doneCount: (count: number) => `Joué ${count} fois`,
    locked: 'Après le quiz',
    lockedLabel: 'Verrouillé : se débloque après le quiz d’arrivée.',
    lockedHint: 'Se débloque après le quiz d’arrivée.',
    toQuiz: 'Faire le quiz',
    duration: (minutes: number) => `${minutes} min`,
    durationLabel: (minutes: number) => `Environ ${minutes} ${plural(minutes, 'minute', 'minutes')}`,
    xp: (xp: number) => `+${xp} XP`,
    xpLabel: (xp: number) => `${xp} points d’expérience à gagner`,
    play: 'Jouer',
    resume: 'Reprendre',
    replay: 'Rejouer',
    progressLabel: (title: string) => `Avancée de ${title}`,
  },
  badges: {
    title: 'Badges',
    count: (earned: number, total: number) => `${earned} sur ${total}`,
    earned: 'Gagné',
    toDiscover: 'À découvrir',
  },
};
