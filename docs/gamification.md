# Quiz, mini-jeux, curseurs et fiche perso

## Parcours

1. À la création du compte, le jeune accepte que ses données soient transmises au Centre des Possibles et à sa psychologue (formulaire d'inscription, hors de ce module).
2. À la première connexion, il arrive sur `/jeune/quiz` : 50 questions en chapitres. Il peut passer une question ou continuer plus tard.
3. Le quiz révèle son clan (type RIASEC dominant) et débloque les jeux de `/jeune/jeux`.
4. `/jeune/fiche` présente sa fiche d'aventurier. Il y corrige ou masque ses détails et dit « C'est moi » ou « Pas moi » sur ce que chaque curseur affiche. Si un curseur bipolaire change de pôle ensuite, son ancien verdict ne s'affiche plus et il peut juger le nouveau.
5. La psychologue voit dans la fiche du jeune les curseurs, chaque partie, chaque réponse et sa source, ainsi que chaque modification du jeune (détail corrigé avec sa réponse d'origine, détail masqué ou remontré, verdict donné, changé ou retiré avec ce qu'il jugeait, réponse changée ou retirée), pour pouvoir en parler avec lui.

## Garde-fous

- Aucune question ni déduction sur la santé, le handicap, l'origine, la famille, la religion, la vie amoureuse ou les opinions. `tests/test_game_content.py` contrôle les textes.
- Le jeune garde la parole sur ce qui le concerne : il corrige ou masque ses détails et donne son verdict sur chaque curseur. Masquer ne change que sa fiche, et l'interface lui dit clairement que la psychologue voit ses réponses et ses changements.
- Côté jeune, pas de pourcentage bas, pas de libellé péjoratif, pas de QI. Les curseurs bipolaires restent neutres et les autres (`kind: unipolar`, quel que soit leur groupe) ne montrent que les points forts. Les attributs de la fiche ne comptent que les points forts, et la fin d'un jeu chronométré ne renvoie que les réussites (voir Calcul).
- Rien de ce qui sert à coter ne part vers le jeune : ni signaux, ni curseurs visés, ni clés de correction, ni sources, ni historique de ses modifications.
- Le MBTI n'est ni normé ni validé. Le nom n'apparaît pas côté jeune, et aucun résultat n'est présenté comme un test MBTI.
- Univers original : aucun nom, personnage ou visuel d'une licence existante.
- Un score de jeu n'est ni un diagnostic ni une norme : la psychologue voit toujours le niveau de preuve.

## Contenu (`backend/app/game/content/`)

| Dossier ou fichier | Rôle |
|---|---|
| `traits/*.json` | Curseurs, regroupés par famille |
| `instruments/*.json` | Quiz, questionnaires et jeux (un fichier par instrument) |
| `sources/*.json` | Références bibliographiques citées par les instruments |
| `clans.json`, `sheet.json` | Clans, attributs de la fiche, niveaux, badges |
| `skill_signals.json` | Effet d'un talent validé sur les curseurs |

### Instrument

```json
{
  "id": "mon_jeu", "version": 1, "order": 10,
  "kind": "quiz | questionnaire | performance",
  "tier": "validated | adapted | custom | performance",
  "title": "…", "tagline": "…", "icon": "…", "duration_min": 5, "xp": 80,
  "requires": ["onboarding"], "replayable": true, "min_answers": 12,
  "source_ids": ["ipip_mini"], "source_note": "Montré au jeune",
  "scoring_note": "Montré à la psychologue",
  "scale": { "min": 1, "max": 5, "labels": ["…"] },
  "chapters": [{ "id": "matin", "title": "…", "intro": "…" }],
  "items": []
}
```

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

| `tier` | Sens | Poids |
|---|---|---|
| `validated` | Items d'un test publié et validé, sans changement de sens | 1 |
| `performance` | Tâche cognitive publiée, score propre à ce jeu | 1 |
| `adapted` | Question du quotidien inspirée d'un test | 0,5 |
| `custom` | Indicateur créé pour le projet | 0,5 |
| `talent` | Talent validé par le jeune dans la discussion | 0,25 |

Une traduction maison d'un test validé reste une traduction non validée : `adaptation` doit le dire.

## Calcul

Chaque réponse produit des signaux de 0 à 100. Un curseur est leur moyenne pondérée par `poids du signal × poids du niveau`. Les réponses du quiz comptent dès qu'elles sont données ; celles des autres instruments comptent quand la partie est terminée. Les jeux chronométrés envoient leurs essais à la fin, et le serveur recalcule leur score (`backend/app/game/performance.py`).

La confiance d'un curseur dépend du poids total de ses signaux : `none` à 0, `low` en dessous de 2, `medium` de 2 à moins de 5, `high` à partir de 5 (`CONFIDENCE_THRESHOLDS` dans `scoring.py`).

### Attributs de la fiche

Un attribut (`sheet.json`) combine plusieurs curseurs. Seuls les points forts comptent : une partie dont le curseur est sous 50 (jeu raté, pôle bas d'un curseur bipolaire) est ignorée. La moyenne pondérée des parties restantes, entre 50 et 100, devient un score de 10 à 20. Sans aucune partie à 50 ou plus, `score` vaut `null` : la fiche affiche « ? » et `reveal_with` propose le premier jeu du catalogue qui nourrit l'un de ces curseurs et reste jouable (un jeu jamais terminé avant un jeu à rejouer).

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

- `POST /runs/<id>/complete` d'un jeu chronométré renvoie dans `metrics` les seules réussites du jeune : la projection `youth` de chaque correcteur (`SCORERS`), par défaut toutes les mesures sans aucun `percent`. Empan : `span`, `trials`, `correct`, `phases.<id>.span`... ; Stroop : `trials`, `best_streak`, `fastest_rt_ms` ; énigmes : `solved`, `best_streak`. La psychologue garde toutes les mesures.
- Un `PUT` de réponse envoyé deux fois donne le même résultat qu'une fois (la dernière valeur gagne). Une partie se modifie sous verrou : rien n'arrive dans une partie déjà terminée (`409 run_closed`).
- Les textes libres (réponses et détails corrigés) refusent les caractères de contrôle et les moitiés de paire UTF-16 (`400`). Un `response_ms` ou `rt_ms` qui n'est pas un nombre fini est ignoré. Le corps d'une requête du jeu est limité à 256 Ko (`413 payload_too_large`).

Psychologue (`/api/backoffice`) : `GET /game/catalog`, `GET /youths/<id>/game`, `GET /youths/<id>/game/runs/<run>`, `GET /youths/<id>/game/traits/<trait>`.

- `GET /game/catalog` : `instruments` (avec `chapters` : identifiant et titre), `sources`, `weights` (poids de chaque niveau de preuve) et `confidence_thresholds` (`{medium: 2, high: 5}`).
- `GET /youths/<id>/game` : chaque curseur garde `verdict` (dernier verdict enregistré) et ajoute `verdict_detail` (`{verdict, label_at_verdict, value_at_verdict, at, stale}`, `stale` quand le curseur a changé de pôle depuis) ; `facts` ajoute `source_instrument_id`, `source_item_id` et `edited_at` (dernière correction de la valeur par le jeune) ; `events` donne les 200 dernières modifications, de la plus récente à la plus ancienne : `{id, kind, subject, ref, before, after, at}`, où `subject` nomme en clair ce qui a changé (« Passion », « Réservé ↔ Sociable », « Quiz d'arrivée · Ta couleur préférée ? ») et `ref` le désigne (`{type: "fact", key}`, `{type: "trait", trait_id}`, `{type: "answer", run_id, instrument_id, item_id}`).
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

La migration `0002` (`down_revision = '0001'`) n'est appliquée nulle part : elle est modifiée sur place tant qu'elle n'est pas fusionnée. La migration `talent_history` de la branche `feat/talent-map` part elle aussi de `0001`. À la fusion dans `feat/talent-map`, mettre `down_revision = 'talent_history'` dans `0002` (ou ajouter une révision de fusion avec `flask db merge`), sinon `flask db upgrade` échoue avec deux têtes de migration.
