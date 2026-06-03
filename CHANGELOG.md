# CHANGELOG — Miny v2.0

_Date : 2026-05-29_

---

## Étape 1 — Routing automatique des questions générales

**Fichiers modifiés :**
- `src/engine/query_router.py`
- `pages/1_Assistant.py`
- `assets/style.css`

**Changements :**
- Ajout de `_is_general_question()` dans `query_router.py` : détecte les questions hors-domaine minier (salutations, définitions, météo, date…) via mots-clés et patterns regex.
- Ajout de `ask_general_stream()` : route directement vers `FALLBACK_MODEL` sans passer par DuckDB ni BM25.
- Dans `1_Assistant.py` : nouveau chemin "general" avant la cascade analytique, badge 💬 violet, notice de switch de modèle silencieuse.
- CSS : ajout de `.badge-general` (fond violet clair).

---

## Étape 2 — Feedback utilisateur amélioré

**Fichiers modifiés :**
- `pages/1_Assistant.py`

**Changements :**
- 👍 tooltip → "Réponse satisfaisante" + message de confirmation "✅ Merci !"
- 👎 tooltip → "Réponse non satisfaisante" + encart de conseils (préciser période, engin, mots-clés métier)
- Les messages apparaissent dans l'historique de la conversation après le clic

---

## Étape 3 — Nettoyage de l'interface

**Fichiers modifiés :**
- `pages/1_Assistant.py`
- `pages/3_Donnees.py`

**Changements :**
- Suppression des 5 boutons chips rapides (Tonnage, Pannes, Carburant, PGES, Documents) — redondants avec les exemples
- Exemples restructurés en 6 catégories × 6 questions : Tonnage & Production, Transport & Navires, Engins & Pannes, Carburant, Objectifs & Perf., PGES & HSE
- Suppression de la section "Indicateurs clés" (4 KPI cards) de la page Données
- Correction double icône calendrier : `icon="📅"` + `📅` dans le texte → `icon="📅"` seul
- Correction source en double : le `_📋 table_` inline de `_src()` est retiré avant affichage analytique (la caption le reprend déjà)

---

## Étape 4 — Section "Tables opérationnelles" : accordéon

**Fichiers modifiés :**
- `pages/3_Donnees.py`

**Changements :**
- "Tables opérationnelles" enveloppée dans `st.expander(..., expanded=True)` — même comportement que "Référentiels"
- Ajout d'une colonne "Actions" dans le tableau des tables (bouton 🔄 Remplacer)

---

## Étape 5 — Section Documents + remplacement de fichiers

**Fichiers modifiés :**
- `pages/3_Donnees.py`
- `pages/4_Parametres.py`

**Changements :**
- Nouvelle section "Documents indexés" dans la page Données : liste les fichiers PDF, DOCX, TXT avec type, nom, boutons 🗑️ Supprimer et 🔄 Remplacer
- Remplacement inline : affiche un `st.file_uploader`, déclenche le pipeline ETL ciblé, affiche la confirmation
- Note ajoutée dans Paramètres → Charger un fichier : "Pour remplacer une table ou un document existant, rendez-vous dans la page Données"

---

## Étape 6 — Correction bug menu "App" parasite

**Fichiers modifiés :**
- `.streamlit/config.toml`

**Changements :**
- Ajout de `[client] showSidebarNavigation = false` pour désactiver l'auto-découverte des pages par Streamlit, qui affichait `app.py` comme "App" dans certaines versions

---

## Étape 7 — Performance : cache et chargement optimisé

**Fichiers modifiés :**
- `pages/1_Assistant.py`

**Changements :**
- `sidebar_stats()` appelé une seule fois (`_sidebar_s`) et réutilisé — élimine le double appel
- Statut Ollama lu depuis `_ollama_status` (dict `@st.cache_resource`) au lieu de refaire `is_available()` + `active_model_name()` à chaque rerun (2 requêtes réseau évitées)
- Badge LLM utilise `_ollama_model` (valeur pré-calculée) partout

**Temps de chargement (estimé) :**
- Avant : ~2 requêtes réseau Ollama + 2 appels `sidebar_stats()` par rerun
- Après : 0 requête réseau Ollama par rerun (cache), 1 appel `sidebar_stats()` par rerun (cache 5 min)

---

## Étape 8 — Design & UX

**Fichiers modifiés :**
- `assets/style.css`
- `pages/4_Parametres.py`

**Changements CSS :**
- Police : `'Inter', 'Helvetica Neue'` partout
- `word-wrap: break-word` sur tous les éléments texte (plus de débordement)
- Sidebar : `background-color: #f8f9fa` (contraste léger)
- Expanders : `font-weight: 600` sur l'entête
- Boutons : `border-radius: 6px`, `font-weight: 500`, `transition: all 0.2s ease`, texte non coupé
- Responsive mobile (< 768px) : header vertical, KPI cards compactes

**Paramètres avancés :**
- `num_ctx` → "Mémoire de conversation" avec `help=` en langage accessible
- `temperature` → "Créativité des réponses" avec `help=` en langage accessible
- Tableau récapitulatif valeurs actuelles + conseils

**Upload :**
- Description claire : formats acceptés, rôle de chaque type (analyse vs recherche documentaire)

---

## Bugs connus restants

- Le bug "App" dans le menu nécessite un Streamlit ≥ 1.36 pour que `showSidebarNavigation = false` soit pleinement pris en compte. Si le bug persiste, vérifiez la version : `.venv\Scripts\python.exe -m streamlit version`
- `ask_general_stream()` nécessite Ollama actif ; si Ollama est hors ligne, la réponse générale affiche le message d'erreur Ollama standard
