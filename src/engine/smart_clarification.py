# -*- coding: utf-8 -*-
"""
src/engine/smart_clarification.py
==================================
Moteur de clarification intelligent pour Miny.

Détecte et corrige automatiquement :
  1. Fautes d'orthographe sur les termes métier miniers
  2. Phrases incomplètes (sujet sans verbe, entité sans période)
  3. Inversion de sujet ("2025 en heures" → "heures en 2025")
  4. Mots-clés manquants (question trop vague)
  5. Ambiguïtés (tonnage sans précision, engin sans type)

Retourne :
  - SmartClarification avec la question reformulée + explication
  - None si la question est claire

Usage dans l'interface :
    from src.engine.smart_clarification import analyser_question
    result = analyser_question("tonage par moi en 2025")
    if result:
        # result.original_q, result.reformulated_q, result.explanation
        # result.confidence, result.category
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Optional

from src.utils.text import norm as _norm


# ════════════════════════════════════════════════════════════════════════════
# 1. DICTIONNAIRE DES TERMES MÉTIER MINIERS ET LEURS VARIANTES
# ════════════════════════════════════════════════════════════════════════════

# Termes canoniques et leurs fautes d'orthographe courantes
# Format : { terme_correct : [variantes_erronées] }
_MINING_VOCAB: dict[str, list[str]] = {
    # Tonnage
    "tonnage":       ["tonage", "tonnages", "tonages", "tonnagge", "tanage"],
    "descendu":      ["dessendu", "descandu", "descandu", "descentu"],
    "descente":      ["dessente", "discente", "descante"],
    "excavé":        ["excave", "escave", "excavee", "excavé"],
    "excavation":    ["escavation", "exavation", "excvation", "excavasion"],
    "transporté":    ["transportee", "tranporte", "transporte", "trnasporte"],
    "transport":     ["transprot", "transpotr", "trnsport"],

    # Heures
    "heures":        ["heure", "heurres", "hure", "hueres"],
    "tambour":       ["tanbour", "tambur", "tamboure", "tambeure"],
    "moteur":        ["moteure", "motur", "motuer"],
    "machine":       ["machnie", "machin", "mahcine"],
    "disponibilité": ["disponibilite", "disponibilté", "disponibilitée"],

    # Engins
    "trencher":      ["trensher", "trencer", "trenscher", "trenche"],
    "tombereau":     ["tomberau", "tomberaux", "tombereaux", "tomberaut"],
    "chargeuse":     ["chargeuses", "charguse", "chargeuz"],

    # Périodes
    "janvier":       ["janvrier", "janiver", "janvie", "janvrier"],
    "février":       ["fevrier", "fevrirer", "fevrie"],
    "trimestre":     ["trimestres", "trimestr", "triemestre", "trimestree"],
    "semestre":      ["semstere", "semestr", "semestree"],
    "mensuel":       ["menusuel", "mensuelle", "mensule"],
    "mois":          ["moiss", "moies"],  # "moi" retiré : pronom français fréquent

    # HSE / PGES
    "obligation":    ["obligasion", "obligaton", "obligaiton"],
    "réalisé":       ["realise", "realisé", "réaliser", "réalisee"],
    "pges":          ["pgse", "pgès", "pge"],
    "avancement":    ["avansement", "avencement", "avancment"],

    # Qualité
    "échantillon":   ["echantillion", "echantilons", "echantillon", "echatillon"],
    "alumine":       ["alumene", "aluminne", "aluminee"],
    "silice":        ["silise", "cilice", "silicee"],
    "teneur":        ["tenneur", "teneuer", "tenur"],

    # Carburant
    "carburant":     ["carbrant", "carburnat", "caburant"],
    "dépotage":      ["depotage", "depoage", "depottage"],
    "citerne":       ["citernes", "citernn", "cisterne"],
}

# Index inversé : variante → terme correct
_VARIANT_TO_CORRECT: dict[str, str] = {}
for _correct, _variants in _MINING_VOCAB.items():
    for _v in _variants:
        _VARIANT_TO_CORRECT[_norm(_v)] = _correct

# Tous les termes canoniques (pour la détection de termes corrects)
_CANONICAL_TERMS: set[str] = {_norm(k) for k in _MINING_VOCAB}

# Préfixes de 2 lettres des termes canoniques (pour pré-filtre edit-distance)
_CANONICAL_PREFIXES: set[str] = {_norm(k)[:2] for k in _MINING_VOCAB if len(_norm(k)) >= 2}

# Mots du français courant qui ne doivent jamais être corrigés en termes miniers.
# Pré-filtre : ces mots sont exclus du chemin edit-distance même s'ils ont ≥5 chars.
_FRENCH_STOP_WORDS: frozenset[str] = frozenset({
    "bonjour", "bonsoir", "merci", "salut", "ciao", "comment",
    "quelle", "quels", "quelles", "pourquoi", "quand", "combien",
    "please", "pouvez", "voulez", "donnez", "afficher", "montrez",
    "toutes", "toujours", "encore", "aussi", "parce", "selon",
    "entre", "depuis", "avant", "apres", "pendant", "autre", "autres",
    "chaque", "plusieurs", "aucune", "aucun", "meme", "ainsi",
    "voici", "voila", "comme", "parmi", "ainsi", "suite", "toute",
})


# ════════════════════════════════════════════════════════════════════════════
# 2. PATTERNS D'INVERSION DE SUJET ET DE STRUCTURE INCORRECTE
# ════════════════════════════════════════════════════════════════════════════

# Détection d'inversion : "2025 en heures machine" → "heures machine en 2025"
_INVERSION_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Année en tête sans préposition
    (
        re.compile(r"^(20\d{2})\s+([\w\s]+?)(?:\s+par\s+)?$", re.I),
        r"\2 en \1",
        "Inversion an/sujet détectée",
    ),
    # "par mois" avant l'année
    (
        re.compile(r"(par\s+mois)\s+(20\d{2})", re.I),
        r"\2 \1",
        "Granularité avant période",
    ),
    # "en" manquant avant l'année : "tonnage 2025" (sans préposition)
    (
        re.compile(r"\b(tonnage|heures?|carburant|pannes?|excavation)\s+(20\d{2})\b", re.I),
        r"\1 en \2",
        "Préposition 'en' manquante",
    ),
]

# ════════════════════════════════════════════════════════════════════════════
# 3. PATTERNS DE QUESTIONS INCOMPLÈTES
# ════════════════════════════════════════════════════════════════════════════

# Termes qui nécessitent une période pour être exploitables
_NEEDS_PERIOD: set[str] = {
    "tonnage", "heures", "carburant", "pannes", "excavation",
    "transport", "production", "qualite", "echantillon",
}

# Termes qui nécessitent une précision sur le type
_NEEDS_PRECISION: dict[str, dict] = {
    "tonnage": {
        "message": "Quel type de tonnage ?",
        "options": ["descendu (mine → stock)", "excavé (terrain)", "transporté (mine → port)", "chargé (navire)"],
        "exemple": "Tonnage **descendu** par mois en 2025",
    },
    "engin": {
        "message": "Quel type d'engin ?",
        "options": ["tombereau (camion-benne)", "trencher TRS N°296", "chargeuse"],
        "exemple": "Pannes **trencher** TRS N°296 en 2025",
    },
    "qualite": {
        "message": "Quel indicateur de qualité ?",
        "options": ["Al2O3 (alumine)", "SiO2 (silice)", "Fe2O3 (fer)"],
        "exemple": "Teneur **Al2O3** des échantillons en 2025",
    },
    "action": {
        "message": "Actions HSE ou PGES ?",
        "options": ["Obligations **HSE** (sécurité interne)", "Actions **PGES** (plan environnemental)"],
        "exemple": "Actions **PGES** non réalisées",
    },
}


# ════════════════════════════════════════════════════════════════════════════
# 4. RÉSULTAT DE CLARIFICATION
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class SmartClarification:
    """
    Résultat de l'analyse d'une question imprécise ou mal formulée.

    Attributes:
        original_q      : question originale de l'utilisateur
        reformulated_q  : question corrigée / reformulée proposée
        explanation     : explication courte du problème détecté
        category        : type de problème ('spelling', 'inversion', 'incomplete', 'ambiguous')
        confidence      : confiance dans la reformulation (0.0 - 1.0)
        corrections     : liste des corrections faites [(original, corrigé)]
        options         : suggestions de précision quand la reformulation n'est pas unique
        needs_confirm   : True = demander confirmation avant d'exécuter la reformulation
    """
    original_q:     str
    reformulated_q: str
    explanation:    str
    category:       str          # 'spelling' | 'inversion' | 'incomplete' | 'ambiguous'
    confidence:     float        # 0.0 – 1.0
    corrections:    list[tuple[str, str]] = field(default_factory=list)
    options:        list[str] = field(default_factory=list)
    needs_confirm:  bool = True

    @property
    def has_change(self) -> bool:
        """True si la reformulation est différente de l'original."""
        return _norm(self.original_q) != _norm(self.reformulated_q)

    def display_message(self) -> str:
        """Message formaté pour l'affichage dans l'UI."""
        lines = [f"💡 **{self.explanation}**"]
        if self.corrections:
            for orig, fixed in self.corrections:
                lines.append(f"  • *{orig}* → **{fixed}**")
        if self.has_change:
            lines.append(f"\n**Vouliez-vous dire :** *{self.reformulated_q}* ?")
        if self.options:
            lines.append("\n**Précisez :**")
            for opt in self.options:
                lines.append(f"  • {opt}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 5. FONCTIONS DE DÉTECTION
# ════════════════════════════════════════════════════════════════════════════

def _edit_distance(a: str, b: str) -> int:
    """Distance de Levenshtein entre deux chaînes (optimisée pour mots courts)."""
    if abs(len(a) - len(b)) > 3:
        return 99
    la, lb = len(a), len(b)
    if la > lb:
        a, b, la, lb = b, a, lb, la
    row = list(range(la + 1))
    for i in range(1, lb + 1):
        prev = row[0]
        row[0] = i
        for j in range(1, la + 1):
            cur = min(row[j] + 1, row[j-1] + 1,
                      prev + (0 if b[i-1] == a[j-1] else 1))
            prev, row[j] = row[j], cur
    return row[la]


def _detect_spelling(question: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Corrige les fautes d'orthographe sur les termes miniers.

    Retourne (question_corrigée, [(mot_original, mot_corrigé)]).
    Utilise d'abord le dictionnaire explicite, puis la distance d'édition ≤ 2.
    """
    words   = question.split()
    result  = []
    changes = []

    for word in words:
        word_norm = _norm(word)
        # 1. Correspondance directe dans le dictionnaire de variantes
        if word_norm in _VARIANT_TO_CORRECT:
            fixed = _VARIANT_TO_CORRECT[word_norm]
            result.append(fixed)
            changes.append((word, fixed))
            continue
        # 2. Déjà un terme canonique → pas de changement
        if word_norm in _CANONICAL_TERMS:
            result.append(word)
            continue
        # 3. Distance d'édition ≤ 2 sur les termes canoniques (mots ≥5 chars)
        # Pré-filtres : exclure les stop-words français et les mots sans préfixe commun
        if len(word_norm) >= 5 and word_norm not in _FRENCH_STOP_WORDS:
            # Optimisation : ne comparer qu'aux canoniques partageant le même préfixe 2-chars
            word_prefix = word_norm[:2]
            if word_prefix in _CANONICAL_PREFIXES:
                best_match: Optional[str] = None
                best_dist  = 99
                for canonical in _MINING_VOCAB:
                    d = _edit_distance(word_norm, _norm(canonical))
                    if d <= 2 and d < best_dist:
                        best_dist  = d
                        best_match = canonical
                if best_match and best_dist <= 2:
                    result.append(best_match)
                    changes.append((word, best_match))
                    continue
        result.append(word)

    return " ".join(result), changes


def _detect_inversion(question: str) -> tuple[str, Optional[str]]:
    """
    Détecte et corrige les inversions de structure.

    Retourne (question_corrigée, explication_ou_None).
    """
    q = question
    for pattern, replacement, explanation in _INVERSION_PATTERNS:
        new_q = pattern.sub(replacement, q)
        if new_q != q:
            return new_q, explanation
    return q, None


def _detect_missing_period(question: str) -> Optional[str]:
    """
    Détecte si une question de calcul manque d'une période temporelle.
    Retourne un message d'aide, ou None si la période est présente.
    """
    ql = _norm(question)
    has_period = bool(re.search(r"\b20\d{2}\b", ql)) or any(w in ql for w in [
        "mois", "trimestre", "semestre", "semaine", "annee",
        "janvier", "fevrier", "mars", "avril", "mai", "juin",
        "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
        "cette annee", "l annee derniere",
    ])
    if has_period:
        return None

    # Domaine analytique présent mais pas de période
    domain_kw  = any(w in ql for w in _NEEDS_PERIOD)
    is_calcul  = any(w in ql for w in ["combien", "total", "bilan", "quel est"])
    is_short   = len(question.split()) <= 4
    question_marks = question.count("?")

    if domain_kw and (is_calcul or question_marks > 0 or is_short):
        return "Période manquante — précisez l'année, le mois ou le trimestre"
    return None


def _detect_ambiguity(question: str) -> Optional[dict]:
    """
    Détecte les ambiguïtés (tonnage sans type, engin sans précision…).
    Retourne un dict de précision, ou None.
    Utilise \b word boundary pour éviter les faux positifs sur des sous-chaînes
    (ex: 'action' dans 'satisfaction', 'engin' dans 'engineering').
    """
    ql = _norm(question)
    for term, info in _NEEDS_PRECISION.items():
        if re.search(rf"\b{re.escape(term)}\b", ql):
            # Vérifier qu'aucune précision n'est déjà présente
            if term == "tonnage":
                has_precision = any(w in ql for w in [
                    "descendu", "descente", "excave", "excavation", "extrait",
                    "transporte", "transport", "paa", "charge", "navire",
                    # Une granularité temporelle fine implique un contexte suffisant
                    "par mois", "par semaine", "par trimestre", "par engin",
                    "mensuel", "hebdomadaire",
                ])
            elif term == "engin":
                has_precision = any(w in ql for w in [
                    "tombereau", "benne", "trencher", "trs", "chargeuse",
                ])
            elif term == "qualite":
                has_precision = any(w in ql for w in [
                    "al2o3", "sio2", "fe2o3", "alumine", "silice", "fer",
                    "echantillon", "navire", "labo",
                ])
            elif term == "action":
                has_precision = any(w in ql for w in ["pges", "hse", "obligation"])
            else:
                has_precision = False

            if not has_precision:
                return {**info, "term": term}
    return None


# ════════════════════════════════════════════════════════════════════════════
# 6. FONCTION PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

def analyser_question(question: str) -> Optional[SmartClarification]:
    """
    Analyse une question et retourne une SmartClarification si un problème est détecté,
    ou None si la question est claire et bien formulée.

    Ordre de priorité :
      1. Fautes d'orthographe (correction automatique, confiance haute)
      2. Inversion de structure (correction automatique, confiance haute)
      3. Période manquante (guidance seulement, pas de reformulation automatique)
      4. Ambiguïté de domaine (options proposées, pas de reformulation)

    Politique de confirmation :
      - Corrections orthographiques simples (1 mot) → needs_confirm=False (auto)
      - Corrections multiples ou inversions → needs_confirm=True
      - Guidance (période, ambiguïté) → needs_confirm=False (affichage seul)
    """
    if not question or not question.strip():
        return None

    # ── 1. Correction orthographique ─────────────────────────────────────────
    corrected_q, spelling_changes = _detect_spelling(question)
    if spelling_changes:
        needs_confirm = len(spelling_changes) > 1
        return SmartClarification(
            original_q     = question,
            reformulated_q = corrected_q,
            explanation    = (
                "Faute(s) d'orthographe détectée(s) sur les termes métier"
                if len(spelling_changes) > 1
                else f"Terme corrigé : *{spelling_changes[0][0]}* → **{spelling_changes[0][1]}**"
            ),
            category       = "spelling",
            confidence     = 0.95 if len(spelling_changes) == 1 else 0.85,
            corrections    = spelling_changes,
            needs_confirm  = needs_confirm,
        )

    # ── 2. Inversion de structure ─────────────────────────────────────────────
    inverted_q, inversion_explanation = _detect_inversion(question)
    if inversion_explanation and _norm(inverted_q) != _norm(question):
        return SmartClarification(
            original_q     = question,
            reformulated_q = inverted_q,
            explanation    = inversion_explanation,
            category       = "inversion",
            confidence     = 0.80,
            needs_confirm  = True,
        )

    # ── 3. Période manquante ─────────────────────────────────────────────────
    period_hint = _detect_missing_period(question)
    if period_hint:
        # Proposer la question avec l'année courante (datetime importé en tête de module)
        current_year = datetime.datetime.now().year
        suggested_q  = f"{question.rstrip('?').strip()} en {current_year} ?"
        return SmartClarification(
            original_q     = question,
            reformulated_q = suggested_q,
            explanation    = period_hint,
            category       = "incomplete",
            confidence     = 0.70,
            options        = [
                f"en **{current_year}** (année courante)",
                f"en **{current_year - 1}** (année précédente)",
                "par **mois** en 2025",
                "au **T1** 2026",
            ],
            needs_confirm  = True,
        )

    # ── 4. Ambiguïté de domaine ──────────────────────────────────────────────
    ambiguity = _detect_ambiguity(question)
    if ambiguity:
        return SmartClarification(
            original_q     = question,
            reformulated_q = question,  # pas de reformulation automatique
            explanation    = ambiguity["message"],
            category       = "ambiguous",
            confidence     = 0.60,
            options        = ambiguity["options"],
            needs_confirm  = False,
        )

    return None


# ════════════════════════════════════════════════════════════════════════════
# 7. DÉTECTION DE QUALITÉ GLOBALE (score 0-10)
# ════════════════════════════════════════════════════════════════════════════

def score_question(question: str) -> dict:
    """
    Calcule un score de qualité de la question (0-10) et retourne un rapport.

    Critères :
      - Présence d'un domaine métier reconnu (+2)
      - Présence d'une période temporelle (+2)
      - Longueur raisonnable (5-20 mots) (+2)
      - Pas de fautes d'orthographe (+2)
      - Présence d'un verbe d'action ou interrogatif (+1)
      - Pas d'ambiguïté sur le type (+1)
    """
    ql = _norm(question)
    score  = 0
    issues = []

    # Domaine métier
    domain_terms = [
        "tonnage", "heures", "carburant", "panne", "excavation",
        "transport", "production", "qualite", "personnel", "objectif",
        "hse", "pges", "navire", "tombereau", "trencher",
    ]
    if any(t in ql for t in domain_terms):
        score += 2
    else:
        issues.append("Aucun terme métier reconnu")

    # Période temporelle
    has_period = bool(re.search(r"\b20\d{2}\b", ql)) or any(w in ql for w in [
        "mois", "trimestre", "semestre", "semaine",
        "janvier", "fevrier", "mars", "avril", "mai", "juin",
        "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
    ])
    if has_period:
        score += 2
    else:
        issues.append("Période temporelle absente")

    # Longueur
    word_count = len(question.split())
    if 3 <= word_count <= 25:
        score += 2
    elif word_count < 3:
        issues.append("Question trop courte")
    else:
        issues.append("Question très longue (>25 mots)")
        score += 1  # partial

    # Orthographe
    _, spelling_errors = _detect_spelling(question)
    if not spelling_errors:
        score += 2
    else:
        issues.append(f"{len(spelling_errors)} faute(s) d'orthographe")

    # Verbe ou interrogatif
    has_verb = any(w in ql for w in [
        "combien", "quel", "quels", "quelles", "quelle", "liste", "bilan",
        "total", "comparer", "afficher", "donner", "montrer",
    ])
    if has_verb:
        score += 1
    else:
        issues.append("Pas de verbe interrogatif clair")

    # Pas d'ambiguïté
    if not _detect_ambiguity(question):
        score += 1
    else:
        issues.append("Ambiguïté sur le type de donnée")

    return {
        "score":  min(10, score),
        "max":    10,
        "pct":    min(100, round(score / 10 * 100)),
        "issues": issues,
        "label":  "Excellente" if score >= 9 else (
                  "Bonne" if score >= 7 else (
                  "Passable" if score >= 5 else "À améliorer")),
    }
