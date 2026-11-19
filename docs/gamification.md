# Quiz, mini-jeux, curseurs et fiche perso

## Parcours

1. À la création du compte, le jeune accepte que ses données soient transmises au Centre des Possibles et à sa psychologue (formulaire d'inscription, hors de ce module).
2. À la première connexion, il arrive sur `/jeune/quiz` : 50 questions dans un ordre tiré au hasard, par séries de 10 (voir « Quiz d'arrivée » ci-dessous). Il peut passer une question ou continuer plus tard.
3. Sa première série de 10 questions débloque les mini-jeux de `/jeune/jeux` (voir « Déblocage ») et la fin du quiz révèle son archétype, un badge tiré de son trait de caractère le plus marqué (voir « Archétype »). L'archétype est recalculé avec toutes ses réponses : si une partie le fait changer, son résultat l'annonce (`previous_archetype` dans la réponse de fin de partie) et la fiche rappelle qu'il peut évoluer au fil des jeux et des talents gardés.
4. `/jeune/fiche` présente sa fiche d'aventurier. Il y corrige ou masque ses détails et dit « C'est moi » ou « Pas moi » sur ce que chaque curseur affiche. Si un curseur bipolaire change de pôle ensuite, son ancien verdict ne s'affiche plus et il peut juger le nouveau.
5. La psychologue voit dans la fiche du jeune les curseurs, chaque partie, chaque réponse et sa source, ainsi que chaque modification du jeune (détail corrigé avec sa réponse d'origine, détail masqué ou remontré, verdict donné, changé ou retiré avec ce qu'il jugeait, réponse changée ou retirée), pour pouvoir en parler avec lui.

### Quiz d'arrivée

- **Ordre.** Chaque partie tire son ordre : chaque question reçoit un rang tiré de l'identifiant de la partie et du sien (`frontend/src/game/seededShuffle.ts`, option `shuffle` de `useRunPlayer`). Une reprise, dans un autre onglet ou sur un autre appareil, suit donc le même ordre, même après une nouvelle version du contenu : une question ajoutée ou retirée ne déplace pas les autres. À l'ouverture, les questions déjà vues passent devant, dans cet ordre : « Retour » remonte la séance question par question, puis les séances précédentes, même pour une partie commencée dans un autre ordre. Une question répondue n'est jamais reposée ; une question passée ne revient que dans la revue de fin. Aucun énoncé ne parle de sa place dans le quiz (`tests/test_game_onboarding.py`).
- **Chapitres.** Ils restent dans le contenu, à la suite : la partie vue par la psychologue range les réponses dans l'ordre du contenu, chapitre par chapitre. Le jeune ne les voit plus.
- **Séries.** Les questions viennent par séries de 10 (`SERIES_SIZE`, `frontend/src/game/quiz/quizLogic.ts`). L'écran de question montre un point par question de la série et le total (« 23 réponses sur 50 ») ; la dernière série ne compte que les questions qui restent (« Question 3 sur 7 »). Une question d'une séance précédente, revue avec « Retour », n'a ni points ni place dans une série : l'écran dit « Tu y as déjà répondu » ou « Tu l'avais passée ». Après 10 questions vues dans la séance (répondues ou passées), s'il en reste de jamais vues, Truffe propose « 10 de plus ! » (« Les 7 dernières ! » en fin de quiz) ou « Je reprends plus tard », qui met la partie en pause et ouvre `/jeune/jeux`. Cet écran montre l'XP gagnée pendant le quiz, les questions à faire avant la révélation et le badge d'archétype encore caché derrière son « ? » : l'archétype reste une surprise jusqu'à la révélation. Ce compte, comme celui de l'écran de reprise (« Plus que 7 questions… »), prend les questions jamais vues, ou les réponses qui manquent pour `min_answers` si elles sont plus nombreuses (beaucoup de questions passées).
- **Séances.** Chaque ouverture du quiz commence une séance : le compte des séries repart de zéro, et l'écran de reprise annonce les réponses déjà données et une nouvelle série de 10 questions jamais vues. Quand toutes les questions ont été vues, la fin ne change pas : revue des questions passées s'il manque des réponses (`min_answers`), puis « Tu as fait le tour ! » et la révélation.
- **Déblocage.** Les mini-jeux exigent le quiz (`requires: ["onboarding"]`), qui fixe `unlocks_after: 10` : ils se débloquent dès que sa partie a vu 10 questions, répondues ou passées (`seen`), ou quand une partie du quiz est terminée. Le serveur décide seul, avec la même fonction pour le refus de `POST /instruments/<id>/runs` (`409 locked`) et pour `locked` dans `GET /api/me/game` (`_satisfied_requirements`, `service.py`) ; le front affiche le seuil qu'il reçoit. L'accueil l'annonce (« Dès la première série, tu débloques les mini-jeux »), l'écran de reprise dit combien de questions manquent, et la fin de la série qui franchit le seuil, même quand une séance précédente s'était arrêtée en cours de série (3 vues, puis la 7e question de la série suivante), le fête : bulle de Truffe, carte « 🎮 Mini-jeux débloqués » au-dessus de l'archétype caché et « Aller aux mini-jeux » à la place de « Je reprends plus tard », pour la même pause. Les séries suivantes et la revue des questions passées n'en parlent plus. Le hub (« Encore 7 questions pour débloquer les mini-jeux. », cartes « Après 10 questions »), la page d'un jeu verrouillé ouverte par son adresse et la quête du quiz sur la fiche disent combien de questions manquent. `must_onboard` ne change pas : le quiz reste l'arrivée tant qu'il n'est ni terminé ni en pause.
- **Pause.** « Continuer plus tard » reste sur chaque question. Tant que le quiz n'est ni terminé ni en pause, `OnboardingGate` renvoie au quiz (`must_onboard`) : la première séance d'un nouveau jeune est donc sa première série, puis le choix. Ouvrir le quiz lève la pause.
- **Temps de réponse.** `response_ms` ne compte ni l'accueil, ni la reprise, ni la fin de série (`markShown` en quittant ces écrans). Sur la fin de série, un appui reçu juste après l'affichage, fin d'un double appui sur la dernière réponse, est ignoré.
- **Hub et fiche.** Tant que le quiz n'est pas terminé, ils y invitent ; dès la première question vue, même passée (`seen` dans `GET /api/me/game`, `answered` ne compte que les réponses), avec le nombre de réponses déjà données (« 10 réponses sur 50 ») et « Continuer », comme l'écran de reprise du quiz.

## Garde-fous

- Aucune question ni déduction sur la santé, le handicap, l'origine, la famille, la religion, la vie amoureuse ou les opinions. `tests/test_game_content.py` contrôle les textes envoyés au jeune (contenu et fichiers `*.fr.ts` hors backoffice) avec la lecture et les termes du garde-fou du chat, plus des mots interdits côté jeune.
- Le jeune garde la parole sur ce qui le concerne : il corrige ou masque ses détails et donne son verdict sur chaque curseur. Masquer ne change que sa fiche, et l'interface lui dit clairement que la psychologue voit ses réponses et ses changements.
- Côté jeune, pas de pourcentage bas, pas de libellé péjoratif, pas de QI. Les curseurs bipolaires restent neutres et les autres (`kind: unipolar`, quel que soit leur groupe) ne montrent que les points forts. Les attributs de la fiche ne comptent que les points forts, et la fin d'un jeu chronométré ne renvoie que les réussites (voir Calcul).
- Rien de ce qui sert à coter ne part vers le jeune : ni signaux, ni curseurs visés, ni clés de correction, ni sources, ni historique de ses modifications, ni le curseur, le pôle ou la valeur qui désignent son archétype.
- Le MBTI n'est ni normé ni validé. Le nom n'apparaît pas côté jeune, et aucun résultat n'est présenté comme un test MBTI.
- L'archétype est un habillage ludique : ni un type de personnalité validé, ni un type MBTI. Son nom et sa description restent positifs, quel que soit le pôle, et la psychologue voit toujours d'après quel curseur il a été attribué.
- Univers original : aucun nom, personnage ou visuel d'une licence existante.
- Un score de jeu n'est ni un diagnostic ni une norme : la psychologue voit toujours le niveau de preuve.

## Contenu (`backend/app/game/content/`)

| Dossier ou fichier | Rôle |
|---|---|
| `traits/*.json` | Curseurs, regroupés par famille |
| `instruments/*.json` | Quiz, questionnaires et jeux (un fichier par instrument) |
| `sources/*.json` | Références bibliographiques citées par les instruments |
| `archetypes.json`, `sheet.json` | Archétypes, attributs de la fiche, niveaux, badges |
| `skill_signals.json` | Effet d'un talent validé sur les curseurs |

### Instrument

```json
{
  "id": "mon_jeu", "version": 1, "order": 10,
  "kind": "quiz | questionnaire | performance",
  "tier": "validated | translated | adapted | custom | performance",
  "title": "…", "tagline": "…", "icon": "…", "duration_min": 5, "xp": 80,
  "requires": ["onboarding"], "replayable": true, "min_answers": 12, "unlocks_after": 5,
  "source_ids": ["ipip_mini"], "source_note": "Montré au jeune",
  "scoring_note": "Montré à la psychologue",
  "scale": { "min": 1, "max": 5, "labels": ["…"] },
  "chapters": [{ "id": "matin", "title": "…", "intro": "…" }],
  "items": []
}
```

`requires` liste les instruments à faire avant celui-ci. Un instrument requis retient les jeux qui l'exigent jusqu'à ce qu'une de ses parties soit terminée, ou, s'il fixe `unlocks_after`, jusqu'à ce que sa partie ait vu ce nombre de questions, répondues ou passées. `unlocks_after` est facultatif : un nombre entier de 1 au nombre de questions de l'instrument, sinon le catalogue refuse de démarrer (un jeu chronométré, sans questions, n'en a pas). Le quiz d'arrivée fixe 10, une série.

Types de questions :

```json
{ "id": "e1", "type": "likert", "prompt": "…", "trait": "extraversion", "keyed": "+",
  "source": { "source_id": "ipip_mini", "ref": "E1", "original": "Texte d'origine", "relation": "translated" } }

{ "id": "q7", "type": "choice", "chapter": "matin", "prompt": "…", "max_choices": 1,
  "options": [{ "id": "a", "label": "…", "emoji": "🔧", "signals": [{ "trait": "riasec_r", "value": 90, "weight": 1 }] }] }

{ "id": "q1", "type": "choice", "prompt": "Ta couleur ?", "fact": "couleur_preferee",
  "fact_label": "Couleur préférée", "allow_text": true, "options": [{ "id": "jaune", "label": "Jaune", "color": "#ffd166" }] }

{ "id": "q2", "type": "text", "prompt": "Ta passion ?", "fact": "passion", "fact_label": "Passion" }
```

`relation` vaut `verbatim`, `translated`, `adapted` ou `inspired`. Une source contient `id`, `title`, `citation`, `url`, `licence`, `validated`, `adaptation` et éventuellement `note`.

Augmenter `version` dès qu'une question est renommée, retirée, ou change de type, d'échelle, d'options ou de cotation : les parties en cours sont alors remises à jour (voir « Versions du contenu »). Une question qui change de sens prend un nouvel identifiant.

### Niveaux de preuve et poids dans les curseurs

| `tier` | Libellé vu par la psychologue | Sens | Poids |
|---|---|---|---|
| `validated` | Test validé | Items d'un test publié et validé, sans changement de sens | 1 |
| `performance` | Tâche cognitive publiée | Tâche cognitive publiée, score propre à ce jeu | 1 |
| `translated` | Test validé, traduction maison non validée | Items d'un test validé, traduits par l'équipe sans étude de la traduction | 0,75 |
| `adapted` | Inspiré de travaux publiés, non validé | Questions écrites par l'équipe à partir d'une théorie ou d'un test publiés | 0,5 |
| `custom` | Indicateur maison | Indicateur créé pour le projet | 0,5 |
| `talent` | Talent validé par le jeune | Talent repéré par Truffe dans la discussion et gardé par le jeune. Un talent que le jeune ajoute lui-même sur sa carte n'a que la catégorie par défaut : il reste sur sa carte et dans le backoffice, mais ne compte ni dans les curseurs, ni dans l'XP, ni dans les badges | 0,25 |

Une traduction maison d'un test validé prend le niveau `translated`, et `adaptation` dit qu'elle n'est pas validée. Citer une théorie (Holland, par exemple) justifie « inspiré de », jamais « test validé ».

Un signal (option d'un choix, ou partie d'une question Likert) peut porter son propre `tier`, qui remplace celui de l'instrument : `{ "trait": "interest_digital", "value": 75, "weight": 0.5, "tier": "custom" }` marque un indicateur maison glissé dans une question sourcée. Ce niveau peut être plus faible que celui de l'instrument, jamais plus fort (`TIER_STRENGTH` dans `catalog.py` : `validated` et `performance`, puis `translated`, `adapted`, `custom`). Le backoffice l'affiche à côté du signal.

Le backoffice montre le libellé envoyé par l'API (`TIER_LABELS` dans `service.py`) ; sa copie dans `frontend/src/game/backoffice/` (libellés, poids, ordre) sert à la légende et à la page Sources, et `tests/test_game_tiers.py` vérifie qu'elle reste identique.

Chaque signal enregistré garde le niveau et le poids de sa réponse : changer le niveau d'un instrument ne réécrit pas les parties terminées. Les versions 2 du Grand Tri, du Miroir et du quiz ont été livrées avant toute base réelle : aucune partie de version 1 n'existe hors des bases de test. Désormais, un changement de version qui touche des parties déjà jouées demande une migration de données.

## Calcul

Chaque réponse produit des signaux de 0 à 100. Un curseur est leur moyenne pondérée par `poids du signal × poids du niveau` (le niveau du signal s'il en porte un, sinon celui de l'instrument). Les réponses du quiz comptent dès qu'elles sont données ; celles des autres instruments comptent quand la partie est terminée. Les jeux chronométrés envoient leurs essais à la fin, et le serveur recalcule leur score (`backend/app/game/performance.py`).

La confiance d'un curseur dépend du poids total de ses signaux : `none` à 0, `low` en dessous de 2, `medium` de 2 à moins de 5, `high` à partir de 5 (`CONFIDENCE_THRESHOLDS` dans `scoring.py`).

### Attributs de la fiche

Un attribut (`sheet.json`) combine plusieurs curseurs. Seuls les points forts comptent : une partie dont le curseur est sous 50 (jeu raté, pôle bas d'un curseur bipolaire) est ignorée. La moyenne pondérée des parties restantes, entre 50 et 100, devient un score de 10 à 20. Sans aucune partie à 50 ou plus, `score` vaut `null` : la fiche affiche « ? » et `reveal_with` propose le premier jeu du catalogue qui nourrit l'un de ces curseurs et reste jouable (un jeu jamais terminé avant un jeu à rejouer).

### Archétype

L'archétype est le badge d'identité du jeune : un nom, une devise, une description et un emoji (`archetypes.json`). C'est un habillage ludique de ses curseurs de caractère, pas un type de personnalité validé ni un type MBTI. Il n'a rien à voir avec les badges de progression de `sheet.json`.

`archetype_for` (`service.py`) le recalcule à chaque lecture, avec tous les signaux du jeune (quiz, questionnaires, jeux et talents validés), comme les curseurs :

1. Seuls comptent les cinq curseurs bipolaires du groupe `personality` qui ont une valeur. Sans aucune valeur, pas encore d'archétype (`null`).
2. Le curseur le plus éloigné de 50 l'emporte ; à égalité, le premier dans l'ordre de `traits/10_personality.json`.
3. S'il ne s'écarte pas de plus de 8 points de 50 (`BALANCED_MARGIN`, la marge qui affiche déjà « Entre les deux » au jeune), c'est l'archétype équilibré, Le Caméléon. Sinon c'est l'archétype de son pôle : `high` au-dessus de 50, `low` en dessous.

| Curseur | Pôle `low` | Pôle `high` |
|---|---|---|
| `extraversion` (Réservé·e ↔ Sociable) | 🏮 La Lanterne | ✨ L'Étincelle |
| `agreeableness` (Franc·he ↔ Conciliant·e) | 🧭 La Boussole | 🤝 Le Pont |
| `conscientiousness` (Spontané·e ↔ Organisé·e) | 🍃 Le Vent | 🧱 La Charpente |
| `emotional_stability` (Intense ↔ Posé·e) | 🔥 La Flamme | ⛰️ Le Roc |
| `openness` (Concret·e ↔ Curieux·se) | 🌳 La Racine | 🔭 L'Horizon |
| Aucun curseur à plus de 8 points de 50 | 🦎 Le Caméléon (`pole: "balanced"`, `trait: null`) | |

Chaque entrée de `archetypes.json` porte `id`, `trait` (`null` pour l'archétype équilibré), `pole` (`high`, `low` ou `balanced`), `name`, `motto`, `description` et `emoji`. Le catalogue refuse de démarrer si un pôle de personnalité n'a pas exactement un archétype, s'il n'y a pas exactement un archétype équilibré, si un archétype vise un curseur qui n'est pas un curseur bipolaire de personnalité, si un pôle est inconnu, si un identifiant est en double ou si un champ manque. `tests/test_game_content.py` relit tous ses textes avec le garde-fou du jeune.

Le jeune reçoit `{id, name, motto, description, emoji, quality}`, où `quality` est le libellé jeune du pôle (« Sociable »), ou « Entre les deux » pour Le Caméléon. La fin de partie renvoie aussi `previous_archetype`, l'archétype d'avant quand la partie l'a fait changer, sinon `null` (comme quand on redemande le résultat d'une partie déjà terminée). Le quiz compte dès les réponses : sa fin révèle l'archétype sans annoncer de changement. Avant cette fin, la fiche garde `identity.archetype` à `null`, comme elle l'annonce (« Ton archétype se révèle à la fin du quiz d'arrivée ») : les réponses d'un quiz en pause et les talents déjà gardés comptent pour les curseurs, et la psychologue voit l'archétype qu'ils donnent, mais le jeune le découvre à la fin du quiz.

Sur sa fiche, une note dit au jeune que l'archétype suit le trait de caractère qui ressort le plus de ses réponses et peut évoluer au fil de ses jeux et de ses talents : les talents gardés des catégories `organisation`, `communication`, `creativite` et `apprentissage` font bouger un curseur de caractère (`skill_signals.json`), sans partie ni annonce. Pour Le Caméléon, cette note et l'indice de fin de partie disent au contraire qu'aucun trait ne ressort nettement pour l'instant (`isBalancedArchetype`, `frontend/src/game/archetype/balanced.ts`, dont l'identifiant est vérifié par `tests/test_game_archetype.py`).

### Verdicts

`PUT /traits/<id>/feedback` enregistre le verdict avec le libellé montré au jeune à ce moment-là (`label_at_verdict` : pôle, « Entre les deux » ou nom du curseur) et la valeur du curseur (`value_at_verdict`), tous deux recalculés par le serveur : ce que le navigateur envoie en plus est ignoré. Côté jeune (fiche, `highlights`), `verdict` vaut `null` quand un curseur bipolaire affiche désormais un autre libellé, pour qu'il puisse juger à nouveau. Le même verdict renvoyé deux fois ne change rien ; deux appuis rapprochés gardent le dernier. Un verdict retiré laisse une trace dans l'historique.

### Versions du contenu

Une partie garde la version de l'instrument (`instrument_version`) et chaque réponse le type et l'échelle de sa question. Quand la version a changé, la partie est remise à jour à la reprise et avant la fin : une réponse dont la question a disparu (ou a été renommée) ou a changé de type ou d'échelle est retirée, les autres sont recalculées avec la définition actuelle et retirées si elles ne sont plus valides. Les parties terminées gardent leur version et leurs résultats.

### Détails passés

Passer une question de détail à laquelle le jeune avait répondu dans la partie retire de sa fiche le détail venu de cette réponse (même instrument, même question), sauf s'il l'a corrigé lui-même. Le retrait apparaît dans l'historique.

## Historique des modifications

`game_events` garde chaque modification du jeune, pour la psychologue seulement : `kind`, `subject` (`fact:<clé>`, `trait:<curseur>`, `answer:<partie>/<question>`), `before`, `after`, `created_at`.

| `kind` | `before` → `after` |
|---|---|
| `fact_edited` | `{label, value}` → `{label, value}` |
| `fact_hidden`, `fact_shown` | `{label, value, hidden}` → `{label, value, hidden}` |
| `verdict_set` | `null` (ou le verdict d'un pôle qui a changé) → `{verdict, label, value}` |
| `verdict_changed` | `{verdict, label, value, at}` → `{verdict, label, value}` |
| `verdict_withdrawn` | `{verdict, label, value, at}` → `{verdict: null, label, value}` (curseur au moment du retrait) |
| `answer_changed` | `{label, value}` → `{label, value}` |
| `answer_retracted` | `{label, value}` → `{label: null, value: null, skipped: true, fact_removed}` |

Une réponse renvoyée à l'identique, un détail réécrit sans changement ou un double appui ne créent pas d'événement.

## API

Jeune (`/api/me/game`) : `GET /`, `POST /instruments/<id>/runs`, `PUT /runs/<id>/answers/<item>`, `POST /runs/<id>/pause`, `POST /runs/<id>/complete`, `GET /sheet`, `PATCH /facts/<clé>`, `PUT /traits/<id>/feedback`.

- `GET /` donne pour chaque instrument `locked` et `unlocks_after` (son seuil, `null` s'il n'en fixe pas), et l'instrument renvoyé avec une partie porte aussi `unlocks_after`. `POST /instruments/<id>/runs` refuse un jeu verrouillé (`409 locked`) avec le vrai seuil : « Ce jeu se débloque après les 10 premières questions du quiz d’arrivée. » (sans seuil, « Ce jeu se débloque après le quiz d'arrivée. »).

- `POST /runs/<id>/complete` renvoie `archetype` et `previous_archetype`, et `GET /sheet` donne `identity.archetype`, `null` jusqu'à la fin du quiz d'arrivée (voir « Archétype ») : jamais le curseur, le pôle ni la valeur qui l'ont désigné.
- `POST /runs/<id>/complete` d'un jeu chronométré renvoie dans `metrics` les seules réussites du jeune : la projection `youth` de chaque correcteur (`SCORERS`), par défaut toutes les mesures sans aucun `percent`. Empan : `span`, `trials`, `correct`, `phases.<id>.span`... ; Stroop : `trials`, `best_streak`, `fastest_rt_ms` ; énigmes : `solved`, `best_streak`. La psychologue garde toutes les mesures.
- Un `PUT` de réponse envoyé deux fois donne le même résultat qu'une fois (la dernière valeur gagne). Une partie se modifie sous verrou : rien n'arrive dans une partie déjà terminée (`409 run_closed`).
- Les textes libres (réponses et détails corrigés) refusent les caractères de contrôle et les moitiés de paire UTF-16 (`400`). Un `response_ms` ou `rt_ms` qui n'est pas un nombre fini est ignoré. Le corps d'une requête du jeu est limité à 256 Ko (`413 payload_too_large`).

Psychologue (`/api/backoffice`) : `GET /game/catalog`, `GET /youths/<id>/game`, `GET /youths/<id>/game/runs/<run>`, `GET /youths/<id>/game/traits/<trait>`.

- `GET /game/catalog` : `instruments` (avec `chapters` : identifiant et titre), `sources`, `weights` (poids de chaque niveau de preuve), `confidence_thresholds` (`{medium: 2, high: 5}`) et `archetypes` (chaque archétype avec `trait`, `pole`, `trait_label` et `pole_label`), affichés sur la page Sources et méthode.
- `GET /youths/<id>/game` : `archetype` ajoute aux champs du jeune `trait`, `pole`, `value` (valeur brute du curseur, `null` pour Le Caméléon), `trait_label` (« Réservé ↔ Sociable ») et `pole_label` (« Sociable », ou « Entre les deux ») ; la synthèse l'explique par le titre du curseur (« 72 % sociable »). Chaque curseur garde `verdict` (dernier verdict enregistré) et ajoute `verdict_detail` (`{verdict, label_at_verdict, value_at_verdict, at, stale}`, `stale` quand le curseur a changé de pôle depuis) ; `facts` ajoute `source_instrument_id`, `source_item_id` et `edited_at` (dernière correction de la valeur par le jeune) ; `events` donne les 200 dernières modifications, de la plus récente à la plus ancienne : `{id, kind, subject, ref, before, after, at}`, où `subject` nomme en clair ce qui a changé (« Passion », « Réservé ↔ Sociable », « Quiz d'arrivée · Ta couleur préférée ? ») et `ref` le désigne (`{type: "fact", key}`, `{type: "trait", trait_id}`, `{type: "answer", run_id, instrument_id, item_id}`).
- `GET /youths/<id>/game/runs/<run>` : chaque ligne ajoute `options` (`[{id, label}]` d'une question à choix) et `scale` (`{min, max, labels}` d'une question Likert, telle que proposée au jeune), `null` sinon. `hidden_by_youth` vaut pour le détail venu de ce même instrument et de cette même question.

Les types TypeScript sont dans `frontend/src/game/types.ts`.

## Développer sans Docker

```bash
cd backend && ~/Project/2026-equipe-04/backend/.venv/bin/python scripts/dev_game.py 5101
cd frontend && VITE_DEV_API_PROXY=http://127.0.0.1:5101 npm run dev -- --port 5201
```

Comptes dans `backend/scripts/dev_game.py`.

`flask seed-demo` (lancé à chaque démarrage du conteneur) fait jouer à chaque jeune de démo les jeux qu'il n'a pas encore commencés, prérequis d'abord : un jeu livré depuis le dernier démarrage apparaît donc aussi dans les fiches de démo, et rien n'est rejoué.

## Intégration

Le jeu (`0002`, tables `game_*`) et l'historique des talents (`talent_history`, table `skill_events`) partent tous deux de `0001`. La révision vide `0003_fusion_jeu_et_historique` les réunit sur la branche `feat/integration`. Ces trois migrations sont désormais figées : tout changement de schéma est une nouvelle révision au-dessus de `0003` (`flask db migrate`). `talent_history` utilise `gen_random_uuid()` : les migrations ne passent que sur Postgres, les tests créent leurs tables avec `create_all` sur SQLite.
