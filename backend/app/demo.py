"""Données de démonstration, entièrement fictives et inspirées du sujet du hackathon."""

YOUTHS = [
    {
        "email_setting": "SEED_YOUTH_EMAIL",
        "display_name": "Sam",
        "share_transcripts": True,
        "game": {
            "skill": 0.9,
            "facts": {"couleur_preferee": "Jaune", "passion": "Mécanique et jeux vidéo"},
            "bias": {
                "extraversion": 28, "agreeableness": 66, "conscientiousness": 74,
                "emotional_stability": 62, "openness": 58, "riasec_r": 88, "riasec_i": 72,
                "riasec_a": 34, "riasec_s": 58, "riasec_e": 36, "riasec_c": 64,
                "interest_digital": 82,
            },
        },
        "messages": [
            ("user", "Rien."),
            ("assistant", "Pas de souci, on n'est pas pressés. Hier, tu as fait quoi de ta journée, même un truc banal ?"),
            ("user", "Bah j'ai réparé le scooter d'un pote dans le garage de la résidence."),
            ("assistant", "Réparer un scooter, ce n'est pas rien. Tu t'y prends comment quand il ne démarre plus ?"),
            ("user", "J'écoute le moteur, je démonte le carbu et je teste pièce par pièce jusqu'à trouver ce qui bloque."),
            ("assistant", "Quand tu dis « je teste pièce par pièce jusqu'à trouver ce qui bloque », je vois quelqu'un qui sait chercher l'origine d'une panne avec méthode. Tu t'y reconnais ?"),
            ("user", "Ouais. Le soir je garde aussi mes petits frères, je les fais manger et je vérifie leurs devoirs."),
            ("assistant", "Tu gères pas mal de choses dans ta soirée. Comment tu t'organises quand tout arrive en même temps ?"),
            ("user", "Et à l'asso du quartier je tiens la caisse pendant les événements, je compte tout à la fin pour que ça tombe juste."),
            ("assistant", "Tenir la caisse et vérifier que tout tombe juste, ça demande de la rigueur. Comment tu fais quand il y a un écart ?"),
        ],
        "skills": [
            {
                "name": "Diagnostiquer une panne",
                "category": "resolution_problemes",
                "description": "Chercher méthodiquement la cause d'un problème technique.",
                "quote": "je teste pièce par pièce jusqu'à trouver ce qui bloque",
                "status": "validated",
            },
            {
                "name": "Tenir une caisse avec rigueur",
                "category": "organisation",
                "description": "Encaisser pendant un événement et vérifier les comptes à la fin.",
                "quote": "je tiens la caisse pendant les événements, je compte tout à la fin pour que ça tombe juste",
                "status": "validated",
            },
            {
                "name": "S'occuper d'enfants",
                "category": "relationnel",
                "description": "Organiser le repas et le suivi des devoirs sur une soirée.",
                "quote": "je les fais manger et je vérifie leurs devoirs",
                "status": "pending",
            },
        ],
    },
    {
        "email": "noa@example.org",
        "display_name": "Noa",
        "share_transcripts": False,
        "game": {
            "skill": 0.8,
            "facts": {"couleur_preferee": "Violet", "passion": "Montage vidéo"},
            "bias": {"extraversion": 60, "openness": 80, "riasec_a": 90, "interest_digital": 75},
        },
        "messages": [
            ("user", "Je fais des montages vidéo pour une chaîne de skate, je coupe, je mets la musique et je publie chaque semaine."),
            ("assistant", "Publier chaque semaine, ça demande de la régularité. Comment tu choisis ce que tu gardes au montage ?"),
        ],
        "skills": [
            {
                "name": "Créer et publier des vidéos",
                "category": "creativite",
                "description": "Monter des vidéos et tenir un rythme de publication.",
                "quote": "je coupe, je mets la musique et je publie chaque semaine",
                "status": "validated",
            },
        ],
    },
]
