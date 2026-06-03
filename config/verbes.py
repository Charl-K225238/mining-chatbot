"""
Verbes d'action → catégorie d'intention.

Utilisé par core/nlp.py (Étape 3) pour détecter l'intention de la question.
Extension de VERBES_ACTION dans src/engine/intention.py.
"""

VERBES_ACTION: dict[str, list[str]] = {
    # Demande générale d'information
    "demander": [
        "dis-moi", "donne-moi", "montre", "affiche",
        "voir", "cherche", "trouve", "indique",
        "qu est-ce que", "qu est-ce qui", "quel est", "quelle est",
        "quels sont", "quelles sont",
    ],
    # Lister des éléments
    "lister": [
        "donner", "montrer", "voir", "connaitre", "savoir",
        "liste", "enumerer", "indiquer",
        "donne moi", "montre moi",
        "cite", "recense", "identifie", "detaille", "decris",
    ],
    # Compter / calculer un total
    "compter": [
        "combien", "nombre de", "total", "somme",
        "frequence", "occurrences", "fois", "quel total",
        "calculer", "calculez",
        "quel est le total", "quelle est la quantite",
        "quelle valeur", "combien de", "quel chiffre", "quel montant",
        "quel est le", "quelle est la",
    ],
    # Filtrer des résultats
    "filtrer": [
        "filtre", "selectionne", "extrait", "isole",
        "uniquement", "seulement", "concernant",
    ],
    # Comparer deux périodes ou sujets
    "comparer": [
        "comparer", "compare", "comparaison",
        "versus", " vs ", "par rapport",
        "difference", "ecart", "evolution", "progression",
        "bilan comparatif", "variation",
    ],
    # Résumer / faire un bilan
    "resumer": [
        "resumer", "resume", "synthese", "bilan", "recapituler",
        "recapitule", "faire le point", "recap", "recapitulatif",
        "etat des lieux", "ou en est", "apercu",
    ],
    # Calculer (moyenne, max, min, classement)
    "calculer": [
        "calcule", "moyenne", "max", "min", "top",
        "classement", "trie", "ordre", "rang",
    ],
    # Analyser / expliquer une cause
    "analyser": [
        "analyser", "analyse", "pourquoi", "comment expliquer",
        "comprendre", "interpreter", "quel impact", "quelle cause",
        "expliquer",
    ],
    # Vérifier une condition
    "verifier": [
        "verifie", "controle", "valide", "est-ce que",
        "y a-t-il", "existe-t-il", "est-il",
    ],
    # Prioriser / recommander des actions
    "prioriser": [
        "prioriser", "priorite", "urgent", "critique", "choisir",
        "recommander", "que faire", "quelle action", "faut-il",
        "lesquelles choisir", "quoi faire en premier",
        "si tu devais", "par ou commencer",
    ],
    # Dimension temporelle (à quelle période)
    "temporel": [
        "au cours de", "pendant", "durant", "en ", "lors de",
        "a travaille", "ont travaille", "a fonctionne",
        "ont fonctionne", "a opere", "ont opere",
    ],
}
