# Strategy

⚠️ **Document normatif — réservé à ChatGPT**  
Ce fichier définit la stratégie globale, les principes méthodologiques et les choix structurants du système.  
Il ne doit **jamais** être modifié par Codex ni par un agent d’exécution automatisé.

---

## Gouvernance documentaire (normatif)

- `strategy.md` est modifié **uniquement** par ChatGPT, et **uniquement** sur demande explicite de l’utilisateur.
- `CONTEXT_SNAPSHOT.md` est le référentiel *as-is* (état réel du code) et ne doit pas être utilisé comme espace de stratégie.
- `strategy.md` est une synthèse des choix structurants et de la doctrine (le « pourquoi / comment ») ; il ne doit pas devenir une checklist d’avancement.
- Les éléments exploratoires ou non actés n’entrent dans `strategy.md` que s’ils sont explicitement décidés comme stratégie.
- Discipline de sortie « copier-coller » :
  - toute commande terminal est fournie dans un bloc de code dédié, sans commentaire inline (compatibilité zsh),
  - tout prompt destiné à Codex est fourni en un seul bloc de code, prêt à être copié-collé.
- Codex commente le code pour expliciter **l’intention, les invariants et les contrats**, pas la mécanique interne.
- Codex maintient `CONTEXT_SNAPSHOT.md` à jour : toute modification fonctionnelle, migration ou test entraîne une mise à jour correspondante du snapshot (*as-is*).
- Codex tient à jour la section **« État des PRs (checklist) »** dans `CONTEXT_SNAPSHOT.md`, avec un statut factuel (*as-is*), sans mélange avec des éléments « à venir ».

---

## Périmètre du document

L’intégralité de cette stratégie s’applique **exclusivement** au module **`discovery_compare`**.

Ce module couvre :
- la découverte de produits comparables,
- la comparaison produit (temps 1),
- la découverte et la comparaison d’offres (temps 2),
- le ranking, la fairness et l’audit,
- l’usage des outils MCP (Playwright, Exa, SERP, DB),
- l’orchestration de l’agent Mistral,
- la constitution progressive de la base produit à partir des snapshots.

Les modules aval (commande, suivi, SAV, comptes, réclamations) :
- ne sont pas couverts par ce document,
- disposent de leurs propres règles et stratégies,
- consomment uniquement les **artefacts de sortie** de `discovery_compare`.

---

## 1. Objectif du système

Construire une plateforme de **découverte, comparaison et sélection de produits et d’offres** à partir d’une URL produit, afin de :

- aider au **choix du produit** avant tout choix de vendeur,
- comparer de manière **équitable, explicable et auditable**,
- constituer une **base produit interne fiable**,
- rester **frugale** en stockage et en calcul, sans sacrifier la fairness.

---

## 2. Principe fondamental : séparation Produit / Offre

### 2.1 Niveau Produit — Product Discovery & Comparison

Objectif : identifier des **références produits comparables** (substituables), indépendamment des vendeurs.

- Comparabilité fondée sur :
  - catégorie,
  - attributs discriminants,
  - technologie / usage,
  - positionnement de gamme.
- Aucune décision de prix ni de vendeur.
- Résultat attendu :
  - un produit source,
  - jusqu’à 5 produits comparables,
  - un tableau comparatif de critères,
  - des plages de prix indicatives.

### 2.2 Niveau Offre — Offer Discovery & Comparison

Objectif : identifier les **offres commerciales** associées à un produit donné.

- Offre = vendeur + prix + conditions (livraison, garantie, retour, disponibilité).
- Les marketplaces et vendeurs sont considérés **après** le choix produit.
- Historisation possible des prix.

---

## 3. Pipelines concurrents et complémentaires

### 3.1 Pipeline P — Product Discovery

Sources mises en concurrence :
- Exa (recherche sémantique web),
- base produit interne (exact puis near match),
- autres sources futures.

Rôle d’Exa :
- proposer des références proches,
- éventuellement inspirer des requêtes SERP,
- **ne jamais décider seul** de la comparabilité finale.

### 3.2 Pipeline O — Offer Discovery

Sources mises en concurrence :
- Exa (optionnel),
- SERP + scraping,
- scraping direct de marketplaces,
- base interne d’offres historisées.

Chaque pipeline dispose de providers interchangeables, d’un arbitrage explicite et d’un format de sortie commun.

---

## 4. Rôle de l’agent Mistral

L’agent Mistral est un **raisonneur sémantique encadré**, jamais une source de faits.

Il intervient uniquement pour :
- la catégorisation produit (avec score de confiance),
- l’évaluation de comparabilité,
- la sélection des critères discriminants,
- la synthèse explicative.

Il ne doit jamais :
- inventer des faits (marque, modèle, prix),
- fusionner des produits,
- favoriser un vendeur ou un domaine,
- modifier directement la base de données.

---

## 5. Fairness et non-déterminisme maîtrisé

Le système accepte un raisonnement non déterministe **à condition** qu’il soit :

- équitable,
- explicable,
- auditable,
- traçable (prompts, modèles, versions).

Le classement final est **déterministe**, calculé à partir de signaux explicites ; le LLM contribue mais n’a jamais le dernier mot.

---

## 6. Stratégie de données et de stockage

### 6.1 Snapshots

- Snapshot des pages dès l’entrée dans le pipeline.
- Snapshots immuables (append-only).
- Utilisés comme preuve, base produit et support de reprocessing.

### 6.2 Digests et consolidation

- Digests dérivés des snapshots.
- Recalculables si la méthode évolue.
- Fusion volontairement conservatrice.

### 6.3 Mécanisme de snapshot et stratégie de fallback

Le **snapshot** constitue le mécanisme central de capture factuelle du système.  
Il est conçu comme une frontière stricte entre le monde externe (web, SERP, marketplaces) et le raisonnement interne du module `discovery_compare`.

#### Objectifs du snapshot

Le snapshot a pour objectifs non négociables :

- figer une **preuve immuable** de la page consultée,
- fournir une **base factuelle unique** pour toute extraction et tout raisonnement,
- permettre le **reprocessing ultérieur** si la méthode évolue,
- garantir l’**auditabilité complète** des décisions prises.

Aucun raisonnement métier, aucun verdict de comparabilité, aucun scoring ne doit être fondé sur des données non issues d’un snapshot.

---

#### Principe général

Toute URL manipulée par le pipeline (produit source, candidat comparable, offre, page SERP) suit le cycle suivant :

1. **Capture de la page**
2. **Extraction structurée**
3. **Production d’un digest déterministe**
4. **Persistance immuable**
5. **Traçabilité via `tool_runs`**

Ce cycle est identique quel que soit le provider utilisé.

---

#### Ordre de priorité des méthodes d’extraction (fallbacks)

L’extraction s’effectue selon une stratégie de fallback stricte et déterministe :

1. **JSON-LD (prioritaire)**
   - Recherche explicite de blocs `application/ld+json`.
   - Extraction normalisée des champs pertinents (produit, offre, prix, marque, identifiants).
   - Si le JSON-LD est valide et exploitable, aucune autre méthode n’est utilisée.

2. **DOM structuré**
   - Extraction via sélecteurs déterministes (balises, microdata, attributs standards).
   - Méthode utilisée uniquement si le JSON-LD est absent, incomplet ou invalide.
   - Les règles d’extraction sont versionnées et auditables.

3. **Fallback minimal**
   - Si aucune extraction structurée fiable n’est possible :
     - capture brute conservée,
     - digest partiel produit,
     - statut marqué comme `partial` ou `indeterminate`.
   - Aucun enrichissement heuristique ou inférence libre n’est autorisé à ce stade.

Le passage d’un niveau à l’autre est **explicitement tracé** dans les métadonnées du snapshot.

---

#### Règles normatives

- Le snapshot est **append-only** : jamais modifié, jamais écrasé.
- Une URL donnée peut avoir **plusieurs snapshots** (dans le temps), mais un snapshot est toujours lié à :
  - un `run_id`,
  - un provider,
  - une méthode d’extraction,
  - une version de règles.
- Toute extraction doit être **rejouable** à partir du snapshot seul.
- Le LLM n’a **jamais accès direct au HTML brut** : il ne consomme que des digests structurés issus du snapshot.

---

#### Interface contractuelle

Le module snapshot expose une interface unique, indépendante du provider :

```python
capture_page(
    url: str,
    context: SnapshotContext,
    provider: SnapshotProviderConfig
) -> PageSnapshotResult
```
Cette fonction garantit :
	•	la capture,
	•	l’extraction avec fallback,
	•	la persistance,
	•	la traçabilité complète.

⸻

#### Intégration dans la stratégie globale

	•	Tous les providers (Playwright MCP, Browser-based, HTTP simple, SERP crawler) utilisent ce module.
	•	Les phases du pipeline (source_snapshot_capture, candidate_snapshot_capture, offers_recall_and_fetch) ne manipulent jamais de contenu web non snapshoté.
	•	La base produit interne est dérivée exclusivement de snapshots validés.

Le snapshot est ainsi le socle factuel, auditable et durable sur lequel repose l’ensemble du système.

## 6.4 Frugalité

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
Toute implémentation doit s’y conformer strictement.