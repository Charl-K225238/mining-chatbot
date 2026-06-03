"""
Dictionnaire de synonymes miniers → forme canonique.

Utilisé par core/nlp.py (Étape 3) pour normaliser les questions.
Extension du dictionnaire de src/engine/intention.py.
"""

DICTIONNAIRE_SYNONYMES: dict[str, list[str]] = {
    # ── Tonnage / production ────────────────────────────────────────────────
    "tonnage descendu": [
        "quantite journaliere descendue", "quantite descendue",
        "production journaliere", "minerai descend", "descente minerai",
        "minerai descendu",
    ],
    "tonnage excave": [
        "tonnage extrait", "volume extrait", "quantite extraite",
        "minerai extrait", "extraction", "excave", "volume excave",
        "excavation prevue",
    ],
    "tonnage transporte": [
        "quantite transportee", "minerai achemine", "achemine au port",
        "envoye au port", "expedie", "arrive port", "depart mine",
    ],

    # ── Engins — normalisations ─────────────────────────────────────────────
    "tombereau": [
        "camion benne", "benne basculante", "dumper",
        "a40g", "volvo", "bh-", "tombereau cat",
    ],
    "tombereaux": [
        "camions bennes", "benner", "dumpers", "flotte tombereaux",
    ],
    "pelle": [
        "pelles", "pe-", "liebherr", "excavatrice", "r9200",
        "chargeuse", "chargeuses",
    ],
    "trencher": [
        "trs n 296", "trs296", "trs n°296", "trs 296", "bulldozer trs",
        "trs", "trenching machine",
    ],

    # ── Utilisation engin ───────────────────────────────────────────────────
    "utilisation": [
        "utilise", "travaille", "en service", "actif",
        "rotations", "voyages", "sessions",
        "hm", "heures moteur", "heures de marche",
        "combien de fois", "nombre de fois", "frequence", "a travaille",
        "ont travaille", "a fonctionne", "ont fonctionne",
    ],

    # ── Qualité ─────────────────────────────────────────────────────────────
    "teneur al2o3": ["taux alumine", "alumine", "al203", "teneur en alumine"],
    "teneur sio2":  ["taux silice", "silice", "si02", "teneur en silice"],
    "teneur fe2o3": ["taux fer", "oxyde de fer", "fe203", "teneur en fer"],

    # ── Carburant ───────────────────────────────────────────────────────────
    "carburant": [
        "gasoil", "diesel", "fuel", "consommation carburant",
        "litre consomme", "plein", "depotage", "ravitaillement",
        "approvisionnement", "citerne",
    ],

    # ── Statuts HSE/PGES ────────────────────────────────────────────────────
    "realise": [
        "termine", "acheve", "accompli", "effectue", "execute", "cloture",
        "done",
    ],
    "non realise": [
        "pas encore fait", "pas realise", "non effectue", "non accompli",
        "restent a faire", "jamais fait", "pas termine", "non fait", "pas fait",
        "non demarre",
    ],
    "en cours": [
        "en-cours", "encours", "en progres", "en avancement", "en train",
        "en progression",
    ],

    # ── Actions / PGES / HSE ────────────────────────────────────────────────
    "pges": [
        "plan gestion", "plan de gestion environnementale",
        "recommandation ande", "plan gestion env",
    ],
    "hse": [
        "hygiene securite environnement",
        "sante securite", "securite travail",
        "action corrective", "actions correctives",
        "mesure corrective", "mesures correctives",
        "action preventive", "actions preventives",
        "urgence hse", "priorite hse",
        "obligation reglementaire",
    ],
    "statut": [
        "avancement", "progression", "etat",
        "bloque", "interrompu",
        "retard", "en retard", "depasse",
        "cloture", "cloturee", "ferme",
    ],
    "non_conformite": [
        "non-conformite", "non conformite", "nc ", " nc", "anomalie",
        "ecart qualite", "deviation",
    ],
    "indemnisation": [
        "compensation", "culture", "communaute",
        "populations", "terres", "degradation terrain",
    ],

    # ── Transport / port ────────────────────────────────────────────────────
    "transport": [
        "achemine", "exporte", "expedie au port",
        "rotation transport", "societe transport",
    ],
    "navire": [
        "bateau", "cargo", "chargement navire", "loading",
        "depart navire", "arrivee navire",
    ],

    # ── Comparaison ─────────────────────────────────────────────────────────
    "comparer": [
        "par rapport a", "difference entre", "ecart entre",
        "evolution de", "bilan comparatif",
        "versus", " vs ", "variation",
    ],

    # ── Objectifs ───────────────────────────────────────────────────────────
    "objectif": [
        "prevu", "prevision", "budget", "cible",
        "planifie", "programme", "target",
        "descente prevue", "excav prevue", "taux accomplissement",
    ],

    # ── Granularités temporelles ────────────────────────────────────────────
    "par mois":      ["mensuel", "mensuelle", "mois par mois", "chaque mois"],
    "par semaine":   ["hebdomadaire", "semaine par semaine", "chaque semaine"],
    "par trimestre": ["trimestriel", "trimestrielle", "chaque trimestre"],
    "par semestre":  ["semestriel", "semestrielle", "chaque semestre"],
}
