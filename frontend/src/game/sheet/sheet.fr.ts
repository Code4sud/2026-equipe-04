/** Textes de la fiche d'aventurier. Tutoiement, phrases courtes, apostrophe typographique. */
const plural = (count: number, one: string, many: string) => (count > 1 ? many : one);
const nbsp = ' ';

/** Guillemets français, avec des espaces insécables pour ne jamais les laisser seuls en bout de ligne. */
export const quote = (text: string) => `«${nbsp}${text}${nbsp}»`;

/** Apostrophe typographique pour les contenus du jeu écrits avec l'apostrophe droite. */
export const typo = (text: string) => text.replace(/'/g, '’');

export const sheetFr = {
  title: 'Ma fiche',
  intro: 'Elle grandit à chaque partie et à chaque talent gardé.',
  transparency: 'La psychologue voit tes réponses et les changements que tu fais ici.',

  hero: {
    kicker: 'Fiche d’aventure',
    archetype: 'Archétype',
    noArchetype: 'encore secret',
    noArchetypeHint: 'Ton archétype se révèle à la fin du quiz d’arrivée.',
    archetypeNote:
      'Il suit le trait de caractère qui ressort le plus de tes réponses : il peut évoluer au fil de tes jeux.',
    level: 'Niv.',
    levelFull: (level: number) => `Niveau ${level}`,
    xp: (xp: number, next: number) => `${xp} / ${next} XP`,
    toNext: (missing: number, level: number) => `Encore ${missing} XP avant le niveau ${level}`,
    xpLabel: (level: number) => `Expérience vers le niveau ${level}`,
    xpValue: (xp: number, next: number) => `${xp} XP sur ${next}`,
  },

  quest: {
    kicker: 'Prochaine quête',
    quizTitle: 'Le quiz d’arrivée',
    quizText: 'Il remplit ton identité et révèle ton archétype. Tu peux faire une pause quand tu veux.',
    quizStart: 'Commencer le quiz',
    quizResume: 'Reprendre le quiz',
    gamesTitle: 'Les mini-jeux',
    gamesText: 'Chaque partie dévoile un attribut caché de ta fiche.',
    gamesCta: 'Voir les jeux',
  },

  identity: {
    title: 'Identité',
    intro: 'Corrige ou masque ce que tu veux.',
    empty: 'Le quiz d’arrivée remplit cette partie : ta couleur préférée, ta passion…',
    emptyCta: 'Aller au quiz',
    edit: (label: string) => `Modifier ${quote(label)}`,
    edited: 'modifié par toi',
    save: 'Enregistrer',
    cancel: 'Annuler',
    hide: 'Masquer de ma fiche',
    hideHint: 'Masqué ici, il reste visible pour la psychologue.',
    invalid: 'Écris entre 1 et 120 caractères.',
    hiddenSummary: (count: number) =>
      `${count} ${plural(count, 'détail masqué', 'détails masqués')} de ta fiche`,
    show: 'Remettre sur ma fiche',
    more: (count: number) => `Voir ${count} ${plural(count, 'autre détail', 'autres détails')}`,
    less: 'Voir moins de détails',
    saved: (label: string) => `${quote(label)} est enregistré.`,
    hidden: (label: string) => `${quote(label)} est masqué de ta fiche.`,
    shown: (label: string) => `${quote(label)} est de retour sur ta fiche.`,
  },

  talents: {
    title: 'Talents',
    count: (count: number) => `${count} ${plural(count, 'gardé', 'gardés')}`,
    intro: 'Repérés avec Truffe ou ajoutés par toi.',
    empty: 'Pas encore de talent gardé. Raconte un truc que t’as fait, même tout bête : Truffe t’aide à repérer ce que tu sais faire.',
    emptyCta: 'Raconter à Truffe',
    pending: (count: number) =>
      `${count} ${plural(count, 'talent t’attend', 'talents t’attendent')} sur Ma carte`,
  },

  attributes: {
    title: 'Attributs',
    intro: 'De 10 à 20. Ils montrent tes forces, jamais une note.',
    /** Lu après le nom de l'attribut par les lecteurs d'écran. */
    spokenScore: (score: number | null) =>
      score === null ? `${nbsp}: à découvrir` : `${nbsp}: ${score} sur 20`,
    play: (title: string) => `Joue à ${quote(title)} pour le découvrir`,
    finish: (title: string) => `Finis ${quote(title)} pour le découvrir`,
    later: 'Tes prochains jeux et talents le révéleront.',
    playAll: (title: string) => `Joue à ${quote(title)} pour les découvrir.`,
    finishAll: (title: string) => `Finis ${quote(title)} pour les découvrir.`,
    laterAll: 'Les jeux les révèlent un à un.',
    laterAllCta: 'Voir les jeux',
  },

  character: {
    title: 'Caractère',
    intro: 'Dis si tu te reconnais. La psychologue voit ton avis, même si tu le changes.',
    empty: 'Joue aux mini-jeux pour dessiner ton caractère.',
    emptyCta: 'Voir les jeux',
    emptyQuiz: 'Le quiz d’arrivée dessine tes premiers traits.',
    yes: 'C’est moi',
    no: 'Pas moi',
    verdictFor: (label: string) => `Ton avis sur ${quote(label)}`,
    pair: (low: string, high: string) => `${low} ou ${high}`,
    leaning: (low: string, high: string, label: string | null) =>
      !label || label === 'Entre les deux'
        ? `Entre ${low} et ${high} : tu es entre les deux.`
        : `Entre ${low} et ${high} : tu penches vers ${label}.`,
    agreed: (label: string) => `Noté : ${quote(label)}, c’est toi.`,
    disagreed: (label: string) => `Noté : ${quote(label)}, ce n’est pas toi.`,
    cleared: (label: string) => `Ton avis sur ${quote(label)} est retiré.`,
    noStrength: 'À découvrir en jouant.',
  },

  badges: {
    title: 'Badges',
    count: (earned: number, total: number) => `${earned} sur ${total}`,
    earned: 'Obtenu',
    goal: 'Objectif',
  },

  download: {
    button: 'Télécharger ma fiche',
    busy: 'Je dessine ta fiche…',
    done: 'Ta fiche est téléchargée.',
    error: 'Le dessin n’a pas marché. Réessaie dans un instant.',
    hint: 'Une image à garder ou à montrer, sans les détails que tu as masqués.',
    file: (name: string) => `fiche-${name}.png`,
  },
};
