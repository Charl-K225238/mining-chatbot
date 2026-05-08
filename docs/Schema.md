# 🧠 DATA SCHEMA CATALOG

> Version : 1.0  
> Objectif : documenter toutes les sources de données, leur rôle métier, leurs structures et leurs relations.


---


# 🧩 1. VUE GLOBALE DU MODÈLE


## 🔥 Domaine Production

- Benene 1 Excavation

- DESCENTE MINERAI

- TRANSPORT MINERAI PAA

- PRODUCTIVITE PORT


## ⛽ Domaine Logistique / Carburant

- CARBURANT (toutes les feuilles)


## 🧪 Domaine Qualité

- Benene 2 Qualite Echantillons

- Benene 2 Qualite Navires

- Benene_3_Regul_Qualité_stock


## 👥 Domaine RH / Opérations

- Benene 0 Personnel

- Benene 1 Shifts Personnel

- Suivi des actions


## 📊 Domaine Planification / Budget

- Budget

- PLAN D'ACTIONS DU PGES

- Suivi des actions


## 📅 Domaine Référentiel

- Benene 0 Liste Engins

- Benene 0 Chargeuses

- Calendar


---


## ⭐ SCHÉMA EN ÉTOILE - CALENDRIER CENTRAL


Le modèle de données suit un **schéma en étoile** avec la table **Calendrier** au centre de toutes les analyses temporelles :


### 🗓️ Table Calendrier (Dimension Centrale)

- **23 colonnes temporelles** : Date, Année, Mois, Jour, Semaine, Trimestre, Saison, etc.

- **Période couverte** : 2023-2026 (1,461 jours)

- **Utilisation** : Filtrage et analyse temporelle de toutes les données opérationnelles


### 🔗 Connexions Temporelles

**Tables opérationnelles connectées au Calendrier :**

- `Benene_1_Excavation` → `Calendrier` (colonne `Date`)

- `DESCENTE MINERAI` → `Calendrier` (colonne `Date`)

- `TRANSPORT MINERAI PAA` → `Calendrier` (colonne `HEURE DEPART`)


**Tables budgétaires connectées au Calendrier :**

- `Budget` → `Calendrier` (colonnes `Année`, `Mois`)

- `PLAN D'ACTIONS DU PGES` → `Calendrier` (colonne `Échéance`)


### 🎯 Avantages du Schéma en Étoile

- **Filtrage temporel unifié** : Toutes les analyses utilisent la même dimension temporelle

- **Performance Power BI** : Optimisé pour les rapports et tableaux de bord

- **Évolutivité** : Facilite l'ajout de nouvelles tables opérationnelles

- **Cohérence temporelle** : Calendrier partagé pour éviter les incohérences


---


# 📁 2. DESCRIPTION DÉTAILLÉE DES FICHIERS


---


## 📁 Benene_0_Chargeuses.xlsx


### 🎯 Rôle métier
Référentiel des chargeuses utilisées sur site avec leur capacité de tonnage.


### 🔗 Utilisation

- Calcul de capacité de production

- Analyse performance engins


- Description : Liste des chargeuses et tonnages pour l'exploitation.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Chargeuses.xlsx › Benene_0_Chargeuses

- Dimensions : 5 × 2


#### 🔠 Colonnes

- `Chargeuse` → `str` — aucune valeur manquante détectée

- `Tonnage` → `float64` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Liste_engins.xlsx


### 🎯 Rôle métier
Inventaire global des engins et équipements du site.


### 🔗 Utilisation

- Référentiel commun entre production, carburant et transport


- Description : Inventaire des engins et équipements miniers.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Liste_engins.xlsx › Benene_0_Liste_engins

- Dimensions : 88 × 3


#### 🔠 Colonnes

- `Type Engin` → `str` — aucune valeur manquante détectée

- `Code / Nom engin / Immatriculation` → `str` — aucune valeur manquante détectée

- `Propriétaire` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Objectifs.xlsx


- Description : Objectifs de production ou de performance.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Objectifs.xlsx › Benene_0_Objectifs

- Dimensions : 780 × 3


#### 🔠 Colonnes

- `Excavation Prévue (T)` → `float64` — aucune valeur manquante détectée

- `Descente Prévue (T)` → `float64` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Personnel.xlsx


### 🎯 Rôle métier
Référentiel des employés.


### 🔗 Utilisation

- Gestion RH

- Affectation des shifts


- Description : Informations sur le personnel et leurs rôles.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Personnel.xlsx › Benene_0_Personnel

- Dimensions : 41 × 3


#### 🔠 Colonnes

- `ID` → `int64` — aucune valeur manquante détectée

- `Métier` → `str` — aucune valeur manquante détectée

- `Nom` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Stocks.xlsx


- Description : Données de stock et de qualité.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Stocks.xlsx › Benene_0_Stocks

- Dimensions : 136 × 3


#### 🔠 Colonnes

- `Stock` → `str` — aucune valeur manquante détectée

- `Qualité à priori` → `str` — aucune valeur manquante détectée

- `commentaire` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Valeurs_initiales.xlsx


- Description : Valeurs initiales associées aux stocks.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Valeurs_initiales.xlsx › Benene_0_Valeurs_initiales

- Dimensions : 27 × 5


#### 🔠 Colonnes

- `Type` → `str` — aucune valeur manquante détectée

- `Stock` → `str` — aucune valeur manquante détectée

- `Valeur` → `float64` — aucune valeur manquante détectée

- `Commentaire` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_0_Zone_excavation.xlsx


- Description : Zones d'excavation répertoriées.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_0_Zone_excavation.xlsx › Benene_0_Zone_excavation

- Dimensions : 22 × 1


#### 🔠 Colonnes

- `Zone d'excavation` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_1_Excavation.xlsx


### 🎯 Rôle métier
Suivi de la production d'excavation (volume, tonnage, zones, équipements).


### 🔗 Utilisation

- KPI production journalière

- Comparaison objectif vs réalisé

- Analyse performance équipements


- Description : Données d'excavation et de tonnage.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_1_Excavation.xlsx › Benene_1_Excavation

- Dimensions : 1107 × 14


#### 🔠 Colonnes

- `Shift` → `float64` — aucune valeur manquante détectée

- `Zone d'excavation` → `str` — aucune valeur manquante détectée

- `Volume excavé (m3)` → `float64` — aucune valeur manquante détectée

- `Tonnage QD` → `float64` — aucune valeur manquante détectée

- `Tonnage MQ` → `float64` — aucune valeur manquante détectée

- `Linéaire jour (m)` → `float64` — aucune valeur manquante détectée

- `Profondeur moyenne (m)` → `str` — aucune valeur manquante détectée

- `Ecart (cm)` → `float64` — aucune valeur manquante détectée

- `Volume excavé tenant compte l'écart(m3)` → `float64` — aucune valeur manquante détectée

- `Tonnage excavé estimé (T)` → `float64` — aucune valeur manquante détectée

- `Tonnage se referant à l'ecart  (T)` → `float64` — aucune valeur manquante détectée

- `Tonnage BQ` → `float64` — aucune valeur manquante détectée

- `Equipement` → `str` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_1_Journal.xlsx


- Description : Journal d'activité ou de suivi.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_1_Journal.xlsx › Benene_1_Journal

- Dimensions : 2389 × 7


#### 🔠 Colonnes

- `Axe` → `str` — aucune valeur manquante détectée

- `Objet` → `str` — aucune valeur manquante détectée

- `Equipement` → `str` — aucune valeur manquante détectée

- `Commentaire` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_1_Shifts_horaires.xlsx


- Description : Données horaires des shifts.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_1_Shifts_horaires.xlsx › Benene_1_Shifts_horaires

- Dimensions : 1163 × 13


#### 🔠 Colonnes

- `Shift` → `float64` — aucune valeur manquante détectée

- `Heure tambour total` → `str` — aucune valeur manquante détectée

- `Heure moteur total` → `str` — aucune valeur manquante détectée

- `Equipement` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


---


## 📁 Benene_1_Shifts_personnel.xlsx


### 🎯 Rôle métier
Affectation du personnel par shift.


### 🔗 Utilisation

- Planification des équipes

- Suivi des heures travaillées


- Description : Informations sur le personnel et leurs rôles.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_1_Shifts_personnel.xlsx › Benene_1_Shifts_personnel

- Dimensions : 6828 × 4


#### 🔠 Colonnes

- `Shift` → `float64` — aucune valeur manquante détectée

- `Opérateur` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_2_Qualite_echantillons.xlsx


- Description : Qualité des échantillons miniers.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_2_Qualite_echantillons.xlsx › Benene_2_Qualite_echantillons

- Dimensions : 1182 × 15


#### 🔠 Colonnes

- `ID ECH` → `str` — aucune valeur manquante détectée

- `POIDS` → `float64` — aucune valeur manquante détectée

- `Tonnage/Ech` → `str` — aucune valeur manquante détectée

- `ZONE` → `str` — aucune valeur manquante détectée

- `STOCK/LOT PLATEAU` → `str` — aucune valeur manquante détectée

- `STOCK DSO` → `float64` — aucune valeur manquante détectée

- `Laboratoire` → `str` — aucune valeur manquante détectée

- `Al2O3` → `float64` — aucune valeur manquante détectée

- `Fe2O3` → `float64` — aucune valeur manquante détectée

- `SiO2` → `float64` — aucune valeur manquante détectée

- `Observations` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_2_Qualite_navires.xlsx


- Description : Qualité des navires.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_2_Qualite_navires.xlsx › Benene_2_Qualite_navires

- Dimensions : 37 × 8


#### 🔠 Colonnes

- `Navire` → `str` — aucune valeur manquante détectée

- `Al2O3 (SGS AFS)` → `float64` — aucune valeur manquante détectée

- `SiO2 (SGS AFS)` → `float64` — aucune valeur manquante détectée

- `Fe2O3 (SGS AFS)` → `float64` — aucune valeur manquante détectée

- `Al2O3 (SGS CHINE)` → `float64` — aucune valeur manquante détectée

- `SiO2 (SGS CHINE)` → `float64` — aucune valeur manquante détectée

- `Fe2O3 (SGS CHINE)` → `float64` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_3_Regul_Qté_stock.xlsx


- Description : Régulation des quantités de stock.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_3_Regul_Qté_stock.xlsx › Benene_3_Regul_Qté_stock

- Dimensions : 233 × 5


#### 🔠 Colonnes

- `Stock` → `str` — aucune valeur manquante détectée

- `Valeur (T)` → `float64` — aucune valeur manquante détectée

- `Commentaire` → `str` — aucune valeur manquante détectée

- `Source` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Benene_3_Regul_Qualité_stock.xlsx


- Description : Données issues du fichier `benene 3 regul qualité stock`.


- Nombre de feuilles : **1**


### 📄 Feuille : Benene_3_Regul_Qualité_stock.xlsx › Benene_3_Regul_Qualité_stock

- Dimensions : 9 × 3


#### 🔠 Colonnes

- `Stock` → `int64` — aucune valeur manquante détectée

- `Qualité` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Budget.xlsx


### 🎯 Rôle métier
Prévision de production et descente mensuelle.


### 🔗 Utilisation

- Planification annuelle

- Comparaison réel vs objectif


- Description : Données de budget de production et de descente.


- Nombre de feuilles : **1**


### 📄 Feuille : Budget.xlsx › Target

- Dimensions : 12 × 4


#### 🔠 Colonnes

- `Année` → `int64` — aucune valeur manquante détectée

- `Mois` → `str` — aucune valeur manquante détectée

- `Tonnage à produire` → `float64` — aucune valeur manquante détectée

- `Tonnage à descendre` → `int64` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 CARBURANT.xlsx


### 🎯 Rôle métier
Suivi de la consommation de carburant par engin, activité et cuves.


### 🔗 Utilisation

- Analyse coût opérationnel

- Calcul productivité carburant

- Suivi consommation par machine


- Description : Données de consommation de carburant et activités.


- Nombre de feuilles : **5**


### 📄 Feuille : CARBURANT.xlsx › LISTE ENGINS MINE

- Dimensions : 88 × 13


#### 🔠 Colonnes

- `ID` → `float64` — aucune valeur manquante détectée

- `Type Engin` → `str` — aucune valeur manquante détectée

- `Code / Nom engin / Immatriculation` → `str` — aucune valeur manquante détectée

- `Propriétaire` → `str` — aucune valeur manquante détectée

- `Activité` → `str` — aucune valeur manquante détectée

- `Consommation moyenne (L/h)` → `float64` — aucune valeur manquante détectée

- `Jauge Arrivée (01/07/2023)` → `str` — aucune valeur manquante détectée

- `Kilométrage (01/07/2023)` → `float64` — aucune valeur manquante détectée

- `Capacité réservoir` → `float64` — aucune valeur manquante détectée

- `Objectif heures travail / jour` → `float64` — aucune valeur manquante détectée

- `Tarif` → `float64` — aucune valeur manquante détectée

- `Centre attitré` → `str` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


### 📄 Feuille : CARBURANT.xlsx › CITERN IVEQI

- Dimensions : 4775 × 6


#### 🔠 Colonnes

- `Engin/Equipement` → `str` — aucune valeur manquante détectée

- `Depotage` → `float64` — aucune valeur manquante détectée

- `Quantité Servie (L)` → `float64` — aucune valeur manquante détectée

- `Quantité Restante (L)` → `float64` — aucune valeur manquante détectée

- `Observation` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : CARBURANT.xlsx › ACTIVITES

- Dimensions : 14272 × 11


#### 🔠 Colonnes

- `MACHINE` → `str` — aucune valeur manquante détectée

- `OPERATEUR PRINCIPAL` → `str` — aucune valeur manquante détectée

- `heure début` → `float64` — aucune valeur manquante détectée

- `heure fin` → `float64` — aucune valeur manquante détectée

- `heure` → `float64` — aucune valeur manquante détectée

- `km début` → `float64` — aucune valeur manquante détectée

- `km fin` → `float64` — aucune valeur manquante détectée

- `Vit. moy (km/h)` → `float64` — aucune valeur manquante détectée

- `Libellé activité` → `str` — aucune valeur manquante détectée

- `Activités` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


### 📄 Feuille : CARBURANT.xlsx › CUVE PETRO-IVOIRE

- Dimensions : 6717 × 8


#### 🔠 Colonnes

- `Engin/Equipement` → `str` — aucune valeur manquante détectée

- `Quantité Initiale Théorique (L)` → `float64` — aucune valeur manquante détectée

- `Depotage` → `float64` — aucune valeur manquante détectée

- `Quantité Servie (L)` → `float64` — aucune valeur manquante détectée

- `Quantité Restante (L)` → `float64` — aucune valeur manquante détectée

- `Jauge` → `float64` — aucune valeur manquante détectée

- `Observation` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : CARBURANT.xlsx › LIBELLE ACTIVITE

- Dimensions : 21 × 1


#### 🔠 Colonnes

- `Libellé activité` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 DESCENTE MINERAI.xlsx


### 🎯 Rôle métier
Suivi du transport de minerai du site vers zones de stockage ou livraison.


### 🔗 Utilisation

- KPI logistique

- Suivi tonnage transporté

- Analyse performance transporteurs


- Description : Descente journalière du minerai.


- Nombre de feuilles : **1**


### 📄 Feuille : DESCENTE MINERAI.xlsx › ALL

- Dimensions : 8228 × 13


#### 🔠 Colonnes

- `Site` → `str` — aucune valeur manquante détectée

- `Responsable site` → `str` — aucune valeur manquante détectée

- `Produit` → `str` — aucune valeur manquante détectée

- `Code / Nom engin / Immatriculation` → `str` — aucune valeur manquante détectée

- `SOCIETE DE TRANSPORT` → `str` — aucune valeur manquante détectée

- `NOMBRE VOYAGE` → `float64` — aucune valeur manquante détectée

- `TONNAGE / VOYAGE` → `int64` — aucune valeur manquante détectée

- `QUALITE` → `str` — aucune valeur manquante détectée

- `QUANTITE JOURNALIERE DESCENDUE (T)` → `int64` — aucune valeur manquante détectée

- `ZONE DE STOCKAGE` → `str` — aucune valeur manquante détectée

- `OBSERVATION` → `str` — aucune valeur manquante détectée

- `N°CAMION` → `str` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 PLAN D'ACTIONS DU PGES.xlsx


- Description : Plan d'actions du PGES.


- Nombre de feuilles : **3**


### 📄 Feuille : PLAN D'ACTIONS DU PGES.xlsx › LEB

- Dimensions : 54 × 9


#### 🔠 Colonnes

- `N°` → `int64` — aucune valeur manquante détectée

- `Actions PGES / Recommandation ANDE` → `str` — aucune valeur manquante détectée

- `Sous actions` → `str` — aucune valeur manquante détectée

- `Livrable` → `str` — aucune valeur manquante détectée

- `Responsable` → `str` — aucune valeur manquante détectée

- `Date de réalisation sous-action` → `str` — aucune valeur manquante détectée

- `Échéance` → `object` — aucune valeur manquante détectée

- `Niveau d'avancement` → `str` — aucune valeur manquante détectée

- `Commentaires` → `str` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


### 📄 Feuille : PLAN D'ACTIONS DU PGES.xlsx › Feuil1

- Dimensions : 25 × 1


#### 🔠 Colonnes

- `Statut de l'action` → `object` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PLAN D'ACTIONS DU PGES.xlsx › EDIT

- Dimensions : 54 × 10


#### 🔠 Colonnes

- `N°` → `int64` — aucune valeur manquante détectée

- `Actions PGES / Recommandation ANDE` → `str` — aucune valeur manquante détectée

- `Sous actions` → `str` — aucune valeur manquante détectée

- `Livrable` → `str` — aucune valeur manquante détectée

- `Responsable` → `str` — aucune valeur manquante détectée

- `Date de réalisation sous-action` → `str` — aucune valeur manquante détectée

- `Échéance` → `object` — aucune valeur manquante détectée

- `Niveau d'avancement` → `object` — aucune valeur manquante détectée

- `Commentaires` → `str` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


---


## 📁 PRODUCTIVITE PORT.xlsx


- Description : Productivité portuaire et suivi des voyages.


- Nombre de feuilles : **6**


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › LOADING RATE

- Dimensions : 205 × 6


#### 🔠 Colonnes

- `QUANTITE CHARGEE` → `float64` — aucune valeur manquante détectée

- `LIEU DE CHARGEMENT` → `str` — aucune valeur manquante détectée

- `ORIGINE STOCK` → `str` — aucune valeur manquante détectée

- `NAVIRE` → `str` — aucune valeur manquante détectée

- `COMMENTAIRE` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › VOYAGE NAVIRE

- Dimensions : 45 × 5


#### 🔠 Colonnes

- `NOM DU NAVIRE` → `str` — aucune valeur manquante détectée

- `OBJECTIF QUANTITE` → `float64` — aucune valeur manquante détectée

- `NOMBRE DE JOURS OPERATIONS PREVUS` → `int64` — aucune valeur manquante détectée


#### 📅 Relation calendrier Power BI
- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › LISTE NAVIRE

- Dimensions : 44 × 12


#### 🔠 Colonnes

- `NAME` → `str` — aucune valeur manquante détectée

- `INFO 1` → `str` — aucune valeur manquante détectée

- `INFO 2` → `str` — aucune valeur manquante détectée

- `INFO 3` → `str` — aucune valeur manquante détectée

- `INFO 4` → `str` — aucune valeur manquante détectée

- `INFO 5` → `str` — aucune valeur manquante détectée

- `INFO 6` → `str` — aucune valeur manquante détectée

- `INFO 7` → `str` — aucune valeur manquante détectée

- `INFO 8` → `str` — aucune valeur manquante détectée

- `INFO 9` → `str` — aucune valeur manquante détectée

- `INFO 10` → `str` — aucune valeur manquante détectée

- `INFO 11` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › REGUL

- Dimensions : 4 × 4


#### 🔠 Colonnes

- `STOCK` → `str` — aucune valeur manquante détectée

- `VALEUR` → `float64` — aucune valeur manquante détectée

- `COMMENTAIRE` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › OBJECTIF JR

- Dimensions : 731 × 2


#### 🔠 Colonnes

- `Tonnage prévue (Kg)` → `int64` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : PRODUCTIVITE PORT.xlsx › INFOS STOCK

- Dimensions : 2 × 1


#### 🔠 Colonnes

- `STOCKS` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 Suivi des actions.xlsx


### 🎯 Rôle métier
Suivi des obligations et actions.


- Description : Suivi des obligations et actions.


- Nombre de feuilles : **2**


### 📄 Feuille : Suivi des actions.xlsx › Obligations

- Dimensions : 40 × 14


#### 🔠 Colonnes

- `Type` → `str` — aucune valeur manquante détectée

- `Titre des obligations` → `str` — aucune valeur manquante détectée

- `Description` → `str` — aucune valeur manquante détectée

- `Direction / Département` → `str` — aucune valeur manquante détectée

- `Statuts` → `str` — aucune valeur manquante détectée

- `Priorité` → `int64` — aucune valeur manquante détectée

- `Périodicité` → `str` — aucune valeur manquante détectée

- `Destinataire` → `str` — aucune valeur manquante détectée

- `Responsable R2M` → `str` — aucune valeur manquante détectée

- `% Avancement` → `float64` — aucune valeur manquante détectée

- `Observations` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


### 📄 Feuille : Suivi des actions.xlsx › Listes de choix

- Dimensions : 20 × 7


#### 🔠 Colonnes

- `Type` → `str` — aucune valeur manquante détectée

- `Catégories` → `str` — aucune valeur manquante détectée

- `PRIORITE` → `float64` — aucune valeur manquante détectée

- `PERIODICITE` → `str` — aucune valeur manquante détectée

- `RESPONSABLE R2M` → `str` — aucune valeur manquante détectée

- `% Avancement` → `float64` — aucune valeur manquante détectée

- `Statuts taches` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ doublons détectés


---


## 📁 TRANSPORT MINERAI PAA.xlsx


### 🎯 Rôle métier
Suivi détaillé du transport vers PAA (Port Autonome / point de livraison).


### 🔗 Utilisation

- Logistique export

- Contrôle poids et conformité transport


- Description : Transport de minerai PAA.


- Nombre de feuilles : **1**


### 📄 Feuille : TRANSPORT MINERAI PAA.xlsx › TRANSPORT MINERAI PAA

- Dimensions : 48074 × 18


#### 🔠 Colonnes

- `HEURE DEPART` → `object` — aucune valeur manquante détectée

- `N° CAMION` → `str` — aucune valeur manquante détectée

- `SOCIETE DE TRANSPORT` → `str` — aucune valeur manquante détectée

- `N° STOCK PRELEVEMENT` → `object` — aucune valeur manquante détectée

- `N° BL` → `float64` — aucune valeur manquante détectée

- `P1 TARE (Kg)` → `object` — aucune valeur manquante détectée

- `POIDS CHARGEE P2 (Kg)` → `float64` — aucune valeur manquante détectée

- `QUANTITE TRANSPORTEE (Kg)` → `object` — aucune valeur manquante détectée

- `N° TICKET PAA` → `object` — aucune valeur manquante détectée

- `P1 TARE (Kg) PAA` → `object` — aucune valeur manquante détectée

- `POIDS CHARGEE P2 (Kg) PAA` → `object` — aucune valeur manquante détectée

- `QUANTITE TRANSPORTEE PAA (Kg)` → `float64` — aucune valeur manquante détectée

- `HEURE ARRIVEE PAA` → `object` — aucune valeur manquante détectée

- `DESTINATION` → `str` — aucune valeur manquante détectée

- `OBSERVATIONS` → `str` — aucune valeur manquante détectée

- `TRANSPORT ANNULE?` → `str` — aucune valeur manquante détectée


#### ⚠️ Qualité des données

- ⚠️ incohérences de types détectées

- ⚠️ doublons détectés


---


---


# 🔗 3. RELATIONS ENTRE TABLES


## 🔥 Production

- Excavation ↔ Descente Minerai ↔ Transport PAA


## ⛽ Carburant

- CARBURANT ↔ ENGINS ↔ ACTIVITES ↔ EXCAVATION


## 🧪 Qualité

- Echantillons ↔ Navires ↔ Stocks


## 👥 RH

- Personnel ↔ Shifts ↔ Activités machines


## 📊 Planification

- Budget ↔ Production réelle


## 📅 Calendrier

- Calendrier ↔ Toutes les tables temporelles


---


# ⚠️ 4. QUALITÉ GLOBALE DES DONNÉES


## Problèmes récurrents

- doublons fréquents

- incohérences de types (object vs float)

- colonnes non normalisées

- manque de clés uniques


## Recommandations

- créer IDs uniques par table

- standardiser types (dates, heures)

- définir clés de jointure

- normaliser noms de colonnes


---


# 🚀 5. UTILISATION DU SCHÉMA


Ce fichier sert à :

- documentation data

- onboarding analystes

- base pour dashboard Power BI

- alimentation chatbot / RAG

- audit qualité données
