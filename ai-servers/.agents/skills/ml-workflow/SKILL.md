---
name: ml-workflow
description: Clustering des pain points pharmacie : Discovery (problème de burnout, scraping PharmQC) → Development (NLP français,...
---

# ML Workflow — Lifecycle canonique end-to-end

> Réf : MIA5100Z « Foundations & Applications of ML » (uOttawa, Dr. A. Omara), Semaine 2.
> Principe : un projet ML suit un **processus structuré, reproductible et cyclique** — pas une suite d'essais.
> Règle d'or (Omara) : _« build it once, automate it forever »_ — la structure apporte approche systématique + reproductibilité + scalabilité.

## 3 phases (vue macro)

| Phase              | Regroupe              | Définition                                                                                  |
| ------------------ | --------------------- | ------------------------------------------------------------------------------------------- |
| **1. Discovery**   | Steps 1-2             | Définition du problème, faisabilité, exploration des données, identification du cas d'usage |
| **2. Development** | Steps 3-6             | Prétraitement, feature engineering, entraînement, validation, expérimentation               |
| **3. Deployment**  | Steps 7-8 (+ retrain) | Mise en service, monitoring, pipelines de réentraînement                                    |

## 8 étapes (vue détaillée)

| #   | Étape                      | Définition (ce que c'est)                                                      | Ce que ça fait (sorties clés)                                                                                                                                                         |
| --- | -------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Problem Formulation**    | Étape initiale critique qui fixe la direction de tout le projet                | Stakeholders, impact business, problème actionnable, **tâche ML** (classif/régression/clustering), critères de succès, scope + timeline                                               |
| 2   | **Data Collection**        | Extraire, curer & collecter les données nécessaires                            | Sources (API/scraping/datasets), features/attributs, contraintes (privacy/qualité/légalité), labels si supervisé                                                                      |
| 3   | **Data Preprocessing**     | Nettoyer, wrangler, curer & préparer les données (**60-70 % du temps**)        | Intégration, nettoyage (doublons), encodage (label/one-hot), valeurs manquantes, scaling, outliers, **split train/val/test**                                                          |
| 4   | **Feature Engineering**    | Créer, transformer ou sélectionner des features pour mieux capter les patterns | Création (combiner colonnes), transformation (normalisation, one-hot), sélection (corrélation/influence)                                                                              |
| 5   | **Modeling / Development** | Choisir & entraîner le meilleur modèle selon objectifs/contraintes             | Model selection (supervisé vs non), training = optimisation des **paramètres** (poids appris)                                                                                         |
| 6   | **Evaluation**             | Mesurer la performance sur **données non vues**                                | Métriques par type (classif : accuracy/precision/recall/F1 ; régression : MSE/MAE/R² ; clustering : silhouette/Dunn), cross-validation (overfitting), model comparison = **champion** |
| 7   | **Deployment**             | Intégrer le modèle dans un environnement de **production**                     | Choix d'environnement, intégration, API, scalabilité, sécurité                                                                                                                        |
| 8   | **Monitoring**             | Garder le modèle efficace & fiable en conditions réelles                       | Performance en prod, **détection de drift** (data/concept/model), anomalies, scalabilité → déclenche le **retraining**                                                                |

> ⚠️ **Deux numérotations dans le cours** (piège quiz) : les **Step 1-8** ci-dessus (slides détaillées) ≠ le diagramme slide 5 « Typical ML Workflow », qui sépare _business goal_ (1) et _ML problem framing_ (2), **regroupe** collection + preprocessing + feature engineering dans une seule phase « Data processing » (3), et fait du **retraining** une phase 8 explicite. Le mapping en 3 phases, lui, reste identique.

## Le cycle (≠ ligne droite)

- Losange **« Are business goals met? »** : si NON → _data augmentation_ / _feature augmentation_ + réentraîner (AVANT le déploiement).
- APRÈS le déploiement : le monitoring détecte le drift → retraining (boucle 8 → 3).
- En production on ne mesure pas l'accuracy (pas de _ground truth_) : on suit le **drift**, avec des métriques différentes de celles du dev.

## Concepts liés (pointeurs, pas de duplication)

- **Drift** (Step 8) : _data drift_ = la distribution des inputs change ; _concept drift_ = la relation features→cible évolue ; _model drift_ = la performance se dégrade (conséquence des deux premiers).
- **Parameters vs hyperparameters** : paramètres = ce que le modèle apprend (poids) ; hyperparamètres = guident _comment_ il apprend (learning rate, nombre de neurones), fixés AVANT le training.
- **Experimentation vs Experiment** : experimentation = stratégie globale (tester N modèles/configs) ; experiment = un run unique.
- **Hypothesis testing** : H₀ (statu quo) vs H₁ (défie le statu quo) ; format « If {variable indépendante} then {variable dépendante} » ; _p-value < α_ (α usuel 0.05) → rejeter H₀ ; Type I = faux positif (rejeter H₀ vrai), Type II = faux négatif (garder H₀ faux). A/B testing = online experiment contre le concept drift.
- **AutoML / ML Pipeline** : automatiser data ingestion → preprocessing → feature selection → training → deployment → monitoring. Suivi d'expériences = MLflow (Databricks). Un pipeline = sous-ensemble automatisé du workflow.

## Application cross-projet (exemple IntelliSoins)

Clustering des pain points pharmacie : **Discovery** (problème de burnout, scraping PharmQC) → **Development** (NLP français, feature engineering, K=11) → **Deployment** (Streamlit/MLX + monitoring du _concept drift_ : Loi 25, nouveaux médicaments, réforme OPQ → réentraîner).

> Cross-réf orchestration (≠ ce fichier) : `pipeline-phases.md` = phases d'un pipeline multi-agent ; `postgresml-usage.md` = ML in-database PostgresML.
