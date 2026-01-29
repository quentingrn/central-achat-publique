# Strategy

Réservé à ChatGPT. Ne pas modifier.

# Strategy — Product & Offer Comparison Platform

⚠️ **Document normatif — réservé à ChatGPT**  
Ce fichier définit la stratégie globale, les principes méthodologiques et les choix structurants du système.  
Il ne doit **jamais** être modifié par Codex ni par un agent d’exécution automatisé.

---

## 1. Objectif du système

Construire une plateforme de **découverte, comparaison et sélection de produits et d’offres**, à partir d’une URL produit fournie par l’utilisateur, avec les objectifs suivants :

- aider à **choisir un produit pertinent** (avant le choix du vendeur),
- comparer de manière **équitable, explicable et auditable**,
- constituer progressivement une **base produit interne fiable**,
- rester **frugale** en stockage et en calcul, sans sacrifier la fairness.

Le système est conçu pour évoluer ensuite vers :
- la **commande**,
- le **suivi de commande**,
- le **service client**,
- la **gestion des comptes et réclamations**,
via des modules séparés.

---

## 1.1 Périmètre du document — Module `discovery_compare`

L’intégralité de la stratégie décrite dans ce document s’applique **exclusivement** au module **`discovery_compare`**.

Ce module couvre :
- la découverte de produits comparables,
- la comparaison produit (temps 1),
- la découverte et la comparaison d’offres (temps 2),
- la méthode de ranking, de fairness et d’audit,
- l’usage des outils MCP (Playwright, Exa, SERP, DB),
- l’orchestration de l’agent Mistral,
- la constitution de la base produit à partir des snapshots.

Les autres modules du système (commande, suivi, service client, comptes, réclamations) :
- ne sont **pas** couverts par ce document,
- disposent de leurs propres stratégies, règles métier et documents normatifs,
- consomment uniquement les **artefacts de sortie** produits par `discovery_compare`.

Ce cadrage évite toute ambiguïté sur le rôle du module et empêche toute extension implicite de responsabilité.
---

## 2. Principe fondamental : séparation Produit / Offre

La stratégie repose sur une distinction stricte entre deux niveaux :

### 2.1 Niveau Produit (Product Discovery & Comparison)

Objectif : identifier des **références produits comparables** (substituables), indépendamment des vendeurs.

- Comparabilité basée sur :
  - catégorie,
  - attributs discriminants,
  - technologie / usage,
  - positionnement de gamme.
- Aucune décision de prix ou de vendeur à ce stade.
- Résultat attendu :
  - un produit source,
  - jusqu’à 5 produits comparables,
  - un tableau comparatif de critères,
  - un résumé des plages de prix (indicatif).

### 2.2 Niveau Offre (Offer Discovery & Comparison)

Objectif : identifier les **offres commerciales** associées à un produit donné.

- Offre = vendeur + prix + conditions (livraison, garantie, retour, disponibilité).
- Les marketplaces et vendeurs sont considérés **après** le choix produit.
- Historisation possible (séries temporelles de prix).

---

## 3. Deux pipelines concurrents et complémentaires

Les deux niveaux ci-dessus sont implémentés via **deux pipelines distincts**, chacun pouvant agréger plusieurs sources mises en concurrence.

### 3.1 Pipeline P — Product Discovery

Sources possibles (concurrentes) :
- Exa (recherche sémantique web),
- Base produit interne (exact match puis near match),
- Autres sources futures (SERP produit, catalogues).

Rôle d’Exa :
- proposer des **références produits alternatives proches**,
- éventuellement générer ou inspirer des requêtes SERP,
- jamais décider seul de la comparabilité finale.

### 3.2 Pipeline O — Offer Discovery

Sources possibles (concurrentes) :
- Exa (optionnel, si des offres structurées sont détectées),
- SERP classique + scraping,
- scraping direct de marketplaces (Amazon, Fnac, LDLC, etc.),
- base interne d’offres historisées.

Chaque pipeline dispose :
- de providers interchangeables,
- d’un orchestrateur d’arbitrage,
- d’un format de résultat commun.

---

## 4. Rôle de l’agent Mistral

L’agent Mistral est un **raisonneur sémantique encadré**, jamais une source de faits.

Il intervient uniquement pour :
- catégorisation produit (avec score de confiance),
- évaluation de comparabilité entre produits,
- sélection et hiérarchisation des critères discriminants,
- synthèse explicative pour l’utilisateur.

Il ne doit jamais :
- inventer des faits (marque, modèle, prix),
- fusionner des produits,
- favoriser un vendeur ou un domaine,
- modifier directement la base de données.

---

## 5. Fairness et non-déterminisme maîtrisé

Le système accepte un **raisonnement non déterministe**, à condition que la méthode soit :

- **équitable (fair)** : mêmes règles, mêmes critères, mêmes pénalités pour tous,
- **explicable** : raisons et signaux toujours exposés,
- **auditable** : prompts, modèles, outputs accessibles en debug,
- **traçable** : décisions associées à des versions de méthode.

Le classement final est :
- calculé de manière **déterministe** à partir de signaux,
- le LLM contribue au score mais n’a jamais le dernier mot.

---

## 6. Stratégie de données et de stockage

### 6.1 Snapshots

- Les pages produits sont **snapshotées dès le début**.
- Les snapshots sont immuables (append-only).
- Ils servent :
  - de preuve,
  - de base à la DB produit,
  - au reprocessing futur.

### 6.2 Digests et consolidation

- Les digests produits sont dérivés des snapshots.
- Ils peuvent être recalculés si la méthode évolue.
- La fusion de produits est volontairement conservatrice.

### 6.3 Frugalité

- Les artefacts lourds sont stockés uniquement s’ils ont une valeur métier.
- Les runs non critiques peuvent être purgés après une durée limitée.
- Un mode debug/audit renforcé peut être activé explicitement.

---

## 7. Architecture cible

- Architecture **modular monolith** avec frontières strictes.
- Chaque domaine métier = un module autonome.
- API unique au départ, extractible plus tard.
- PostgreSQL comme base de vérité, migrations strictes et verrouillées.

---

## 7.1 Étanchéité stricte des contextes de modules (Bounded Contexts)

Chaque module du système constitue un **contexte métier étanche** (*bounded context*).

Règles non négociables :

- Les modèles de domaine (`domain/`) d’un module **ne doivent jamais être importés** par un autre module.
- Les règles métier, invariants et décisions internes **ne fuient pas** hors du module.
- Aucun accès direct aux tables, repositories ou schémas DB d’un autre module.
- Les intégrations inter-modules passent exclusivement par :
  - des **interfaces explicites** (ports),
  - des **DTO / schémas d’échange** dédiés,
  - ou des **événements métier** clairement typés (le cas échéant).

En particulier :
- Le module `discovery_compare` expose des **artefacts de décision** (résumés, sélections, comparaisons),
- Les modules avals (commande, suivi, SAV, comptes, réclamations) **consomment ces artefacts** sans connaître :
  - les providers utilisés (Exa, SERP, scraping, DB),
  - les prompts,
  - les outils MCP,
  - ni les mécanismes internes de scoring ou de comparabilité.

Cette étanchéité garantit :
- la lisibilité de l’architecture,
- l’auditabilité des décisions,
- la possibilité d’extraire un module en service indépendant,
- l’absence de couplage caché entre domaines.

Toute violation de cette règle est considérée comme une dette architecturale bloquante.

---

## 8. Évolutivité

La stratégie vise à permettre, sans refonte majeure :
- l’ajout de nouveaux providers (produit / offre),
- l’amélioration progressive de la DB interne,
- l’intégration de modules commande, suivi, SAV, comptes,
- le remplacement ou la spécialisation du LLM.

---

## 9. Décisions stratégiques figées

1. Séparation stricte produit / offre.
2. Pipelines concurrents dès le départ (Exa vs SERP vs DB).
3. Agent Mistral = raisonneur, jamais source de faits.
4. Fairness procédurale > déterminisme strict.
5. Snapshots conservés comme actif central.
6. Frugalité par défaut, audit renforcé à la demande.

---

Ce document constitue la référence stratégique de haut niveau du projet.
Toute implémentation doit s’y conformer.