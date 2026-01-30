# Strategy

Réservé à ChatGPT. Ne pas modifier.

## Gouvernance documentaire (normatif)

- `strategy.md` est modifié **uniquement** par ChatGPT, et **uniquement** sur demande explicite de l’utilisateur.
- `CONTEXT_SNAPSHOT.md` est le référentiel *as-is* (état réel du code) et ne doit pas être utilisé comme espace de stratégie.
- `strategy.md` est une synthèse des choix structurants et de la doctrine (le « pourquoi / comment »), et ne doit pas devenir une checklist d’avancement.
- Les éléments exploratoires ou non actés n’entrent dans `strategy.md` que s’ils sont explicitement décidés comme stratégie.
- ChatGPT applique systématiquement une discipline de sortie « copier-coller » :
  - toute commande terminal est fournie dans un bloc de code dédié, sans commentaire inline (compatibilité zsh),
  - tout prompt destiné à Codex est fourni en un seul bloc de code, prêt à être copié-collé.
- Codex commente le code pour expliciter **à quoi** il sert (intention, invariants, contrats), pas **comment** il fonctionne (le code doit rester auto-explicatif).
- Codex maintient `CONTEXT_SNAPSHOT.md` à jour : toute modification fonctionnelle/migration/test doit entraîner une mise à jour correspondante du snapshot, reflétant l’état réel (as-is) et balisant explicitement tout élément « à venir ».

## current_implementation

Espace **provisoire** de travail (réservé à ChatGPT) destiné à approfondir un point précis du fonctionnement **en cours de conception**.

Règles d’usage (normatif) :
- Ce bloc sert à détailler temporairement **un sujet à la fois** (contrats, phases, invariants, schémas, critères d’arbitrage), afin de converger vers une décision validée.
- Il n’a pas vocation à refléter l’état réel du code : l’avancement et le *as-is* restent exclusivement dans `CONTEXT_SNAPSHOT.md`.
- Une fois le point validé, son contenu est **retiré** de cette section et :
  - soit intégré dans les sections stratégiques pérennes de `strategy.md` (doctrine/invariants),
  - soit basculé dans la section **« À venir / Non implémenté »** de `CONTEXT_SNAPSHOT.md` comme élément *to be implemented* (avec statut).
- Cette section doit être **vidée régulièrement** ; elle ne doit pas accumuler des décisions anciennes ni devenir une checklist.

Sujet courant :
- Implémentation de l’agent intégré (Mistral + MCP Playwright/Exa/DB) et de son diagnostic.

### Règles d’implémentation (normatif — périmètre courant)

1) **Périmètre module**
- Tout le code métier relatif à l’agent et au debug vit dans **`modules/discovery_compare/`** (bounded context).
- `apps/api/` se limite à la composition FastAPI et au routing HTTP ; il ne contient pas de logique métier `discovery_compare`.

2) **Étanchéité des contextes**
- Aucun import de `modules/discovery_compare/domain/` depuis un autre module.
- Pas d’accès direct inter-modules aux tables/repositories : échanges via DTO/ports uniquement.

3) **Migrations DB : règles normatives**
- Toute évolution de schéma nécessaire à `discovery_compare` (snapshots, runs, events, tool_runs, llm_runs, prompts, offers, etc.) respecte strictement les verrous :
  - Alembic = source de vérité,
  - single-head permanent,
  - migrations immuables,
  - smoke DB upgrade head,
  - drift guard bloquant par défaut.
- Aucune “astuce dev” ne doit contourner ces règles en dehors des overrides explicitement prévus.

4) **Contract-first**
- Les entrées/sorties du run sont **JSON strict** (schémas versionnés, validés Pydantic).
- Chaque phase doit produire des traces structurées (run_events) et des références vers snapshots / tool_runs / llm_runs.

5) **Facts-first**
- Les faits proviennent des tools MCP et de la DB ; le LLM raisonne uniquement sur des faits fournis.
- Toute incertitude est explicite (`indeterminate` / `missing_critical[]`).


6) **Fairness procédurale**
- Les providers sont mis en concurrence (Exa vs DB pour produit ; SERP/scraping vs DB pour offres ; Exa offres optionnel).
- Le ranking final est déterministe et auditable (breakdown explicite).

7) **Variables d’environnement**
- Toute nouvelle variable d’environnement introduite par `discovery_compare` (providers, modèles, endpoints MCP, flags debug/audit, caches, timeouts) doit être :
  - documentée dans `.env.example` (nom, valeur par défaut si applicable, commentaire court),
  - reflétée dans la configuration typée (ex. Pydantic Settings),
  - et mentionnée dans `CONTEXT_SNAPSHOT.md` lors de son introduction (statut *as-is*).

### Objectif

Définir une stratégie d’implémentation **contractuelle** (phases, schémas, diagnostics) pour un agent Mistral intégré, capable de :
- produire une liste de produits comparables (temps 1),
- produire une liste d’offres normalisées (temps 2),
- exposer un debug suffisant (prompts, outputs, snapshots, timeline),

tout en respectant la séparation **Produit / Offre**, la **fairness procédurale** et l’auditabilité.

### Stratégie d’implémentation (agent intégré v1)

#### 0) Préambule
Objectif v1 : un run complet qui retourne :
- top 5 comparables (temps 1),
- offres normalisées pour source + comparables (temps 2),
- diagnostic exploitable (prompts, outputs, snapshots, timeline).


Principe : l’agent est un orchestrateur qui déclenche tools/DB, appelle le LLM sur des faits, et produit un JSON final validé.

#### Agent Mistral : lifecycle, création vs utilisation et versionning (normatif)

Pour garantir une utilisation efficace, traçable et auditée de Mistral, l’agent est découpé en deux phases conceptuelles :

1) **Phase de création (initialisation de l’agent)**
   - Elle consiste à instancier l’agent Mistral avec :
     - les **prompts système** et **prompts tâche** versionnés,
     - les **JSON-schema** associés aux tâches LLM critiques,
     - les paramètres d’inférence (modèle, réglages).
   - Cette initialisation est effectuée **au démarrage de l’application** ou **lorsqu’une version de prompt/schema change**.
   - L’agent ainsi créé est associé à une **version explicite** (`agent_version`), dérivée des hachages des prompts + schémas.
   - Aucun code métier ne doit être exécuté à ce stade : il s’agit uniquement de charger et de valider la configuration de l’agent.

2) **Phase d’utilisation (exécution des runs)**
   - Une fois créé, l’agent est **réutilisé pour chaque invocation du pipeline** tant que la configuration/versionning ne change pas.
   - À chaque run, l’agent reçoit un **input JSON structuré**, exécute les tâches LLM avec JSON-schema, et renvoie des sorties validées.
   - L’agent n’est **pas recréé à chaque utilisation**, ce qui optimise la latence et réduit les coûts.

3) **Versionning de l’agent (normatif)**
   - Toute modification d’un **prompt système ou tâche** ou d’un **JSON-schema officiel** déclenche la création d’une *nouvelle version d’agent*.
   - L’ancien agent reste référencé pour le debug et l’audit.
   - Chaque run LLM persiste :
     - l’identifiant de version de l’agent (`agent_version`),
     - les **hashes prompts + schemas** utilisés,
     - le modèle et les paramètres d’inférence.
   - Les diagnostics exposés doivent permettre de retracer précisément **quelle version d’agent** a généré quelles sorties.

4) **Contrat de stabilité**
   - Un `agent_version` donné doit produire des sorties *consistantes* contre les mêmes inputs et mêmes schémas, indépendamment du nombre d’exécutions.
   - La trace complète (prompts, schemas, modèle, sortie brute et validée) doit être persistée au moins dans les `llm_runs` pour chaque phase LLM utilisée.

Ce schéma garantit que l’agent est **performant, auditable et versionné** sans être reconstruit inutilement à chaque requête, tout en conservant la traçabilité complète de ses décisions et de sa configuration.

#### Règles de sortie LLM (normatif — Mistral)

- L’agent doit exploiter explicitement les **modes de sortie structurés** de Mistral :
  - `json-schema` (prioritaire),
  - `json` (toléré si `json-schema` non disponible),
  - `text` **strictement interdit** comme source de données métier.

- Toute tâche LLM participant à une décision métier (comparabilité, critères, scoring, verdict) :
  - doit être formulée avec un **JSON-schema explicite** dérivé des schémas Pydantic v1,
  - doit produire une sortie validable automatiquement contre ce schéma.

- Pipeline de validation obligatoire pour chaque `llm_run` :
  1) sortie brute renvoyée par le modèle,
  2) validation contre le JSON-schema attendu,
  3) soit :
     - sortie validée (consommable par l’agent),
     - soit échec de validation ⇒ phase marquée `error` ou `indeterminate`.

- Aucune extraction heuristique de texte libre (regex, parsing ad hoc) n’est autorisée pour alimenter :
  - les verdicts,
  - les scores,
  - les critères,
  - les décisions de ranking.

- Les sorties texte libres sont autorisées **uniquement** :
  - pour des explications UX postérieures à la décision,
  - hors pipeline décisionnel,
  - sans impact sur les artefacts de sortie contractuels.

- Debug et audit (obligatoire) :
  - pour chaque `llm_run`, persister :
    - le prompt complet (texte),
    - le JSON-schema demandé,
    - la sortie brute du modèle,
    - la sortie validée ou les erreurs de validation,
    - le modèle et les paramètres d’inférence.

#### 1) Contract-first : schémas et phases
- Définir et figer les schémas Pydantic v1 :
  - `AgentRunOutputV1`, `ProductDigestV1`, `ComparableV1`, `OfferV1`,
  - `RunDiagnosticsV1`, `FairnessMetricsV1`.
- Règle : JSON final invalide ⇒ run `error` avec diagnostic.
- Figer les noms de phases v1 (source unique : code + DB + debug) :
  1. `source_snapshot_capture`
  2. `product_candidates_recall`
  3. `candidate_snapshot_capture`
  4. `comparability_gate`
  5. `criteria_selection`
  6. `product_comparison_build`
  7. `offers_recall_and_fetch`
  8. `offers_normalize_and_dedupe`
  9. `final_response_assemble`

#### 2) Socle debug “run-centric” (à construire en premier)
- Ajouter via migrations (M1..M6) les entités nécessaires au debug :
  - `compare_runs`, `run_events`, `tool_runs`, `llm_runs`, `prompts`, `page_snapshots`.
- Implémenter un `RunRecorder` (service interne) pour centraliser :
  - création de run, événements de phase,
  - enregistrement tool_runs/llm_runs,
  - liens vers snapshots/artefacts,
  - finalisation du run.
- Exposer les endpoints debug MVP :
  - `GET /v1/debug/compare-runs/{run_id}`
  - `GET /v1/debug/llm-runs/{id}`
  - `GET /v1/debug/tool-runs/{id}`
  - `GET /v1/debug/snapshots/{id}`
  - `GET /v1/debug/prompts/{id}`

#### 3) Providers + stubs (tests sans réseau)
- Définir les ports (interfaces) :
  - `SnapshotProvider`, `ProductCandidateProvider`, `OfferCandidateProvider`, `LlmJudge`.
- Fournir des implémentations **stubs** déterministes (fixtures) pour :
  - exécuter l’orchestrateur,
  - valider schémas + persistance debug,
  - éviter les appels réseau en CI.

#### 4) Orchestrateur (AgentRunner) avec phases contractuelles
- Implémenter `AgentRunner` (application layer) :
  - exécution séquentielle des phases,
  - enregistrement `run_events`,
  - appels providers,
  - assemblage de la réponse finale.
- Politique d’échec :
  - une phase en erreur est tracée,
  - continuation si possible (phases ultérieures `skipped` si dépendances manquantes),
  - sinon run `error`,
  - la réponse contient toujours `run_id` + diagnostics minimaux.

#### 5) Comparability Gate + ranking déterministe
- Hard-filters déterministes (catégorie/type incompatibles, contradictions d’identifiants).
- LLM judge encadré (JSON strict) :
  - `verdict`, `score (0..1)`, `reasons_short[]`, `signals_used[]`, `missing_critical[]`.
- Ranking final déterministe avec breakdown explicite (fairness) :
  - `comparability_score` (borné),
  - `coverage_score`,
  - `identity_strength`,
  - cap/penalty de diversité domaine.

#### 6) Intégration MCP progressive (Playwright puis Exa)
- Intégrer Playwright MCP en premier :
  - `source_snapshot_capture` + `candidate_snapshot_capture`,
  - extraction digest déterministe (JSON-LD prioritaire, DOM fallback),
  - persistance `page_snapshots` + `tool_runs`.
- Intégrer Exa MCP ensuite :
  - `product_candidates_recall`,
  - persistance de la requête, top N résultats, scores/snippets (tool_run),
  - dédoublonnage + sélection N candidats à snapshotter.

#### 7) Offres v1 (pragmatique)
- Implémenter un provider “SERP/scrape” minimal (ou placeholder) :
  - extraire au moins `offer_url`, `seller`, `price`, `currency`, conditions si disponibles,
  - tracer `evidence` (source/champ/snapshot).
- Normalisation + dédoublonnage :
  - clé principale `offer_url`,
  - heuristiques vendeur/prix/devise.

#### 8) Stratégie de tests (diagnostic inclus)
- Unit (sans DB) :
  - extraction digest (fixtures),
  - hard-filters comparabilité,
  - ranking déterministe.
- Intégration (Postgres, providers stubs) :
  - run complet `/v1/discovery/compare` sans réseau,
  - assertion que chaque phase crée un `run_event`,
  - `llm_runs` référencent des `prompts`,
  - `page_snapshots` existent et sont référencés,
  - endpoints debug retournent timeline + prompts + outputs.
- Intégration MCP simulée (adapters mockés) :
  - vérifier wiring + persistance des `tool_runs` sans réseau.

#### 9) Critère “Done v1”
- `/v1/discovery/compare` renvoie un JSON validé (comparables + offers + diagnostics).
- Le debug expose modèle+prompts, outputs tools/LLM, snapshots, timeline, breakdown scoring.
- Les tests garantissent la présence et la stabilité de ces éléments.
- Les migrations respectent strictement M1..M6 (single-head, immutabilité, smoke DB, drift guard).

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
Toute implémentation doit s’y conformer.Ò