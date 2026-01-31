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

- Capture logique des pages dès l’entrée dans le pipeline (facts-first).
- Persistance **append-only** des résultats structurés (extraction + digest) pour garantir la traçabilité de la méthode.
- La conservation de la **preuve brute** (HTML/screenshot/HAR) est **optionnelle** et réservée au **debug/audit** (voir §6.3).
- Utilisés comme base produit et support de reprocessing **à partir des données structurées** (pas du HTML brut par défaut).

### 6.2 Digests et consolidation

- Digests dérivés des snapshots.
- Recalculables si la méthode évolue.
- Fusion volontairement conservatrice.

### 6.3 Mécanisme de snapshot et stratégie de fallback

Le **snapshot** constitue le mécanisme central de capture factuelle du système.  
Il est conçu comme une frontière stricte entre le monde externe (web, SERP, marketplaces) et le raisonnement interne du module `discovery_compare`.

#### Objectifs du snapshot

Le snapshot a pour objectifs non négociables :

- produire des **faits structurés** (extraction + digest) utilisés par le raisonnement métier (facts-first),
- garantir la **traçabilité de la méthode** (provider, fallback, signaux, erreurs),
- permettre le **reprocessing** si la méthode d’extraction évolue (à partir des données structurées persistées),
- fournir un **mode debug/audit** activable explicitement, capable de conserver une preuve brute lorsque nécessaire.

Aucun raisonnement métier, aucun verdict de comparabilité, aucun scoring ne doit être fondé sur des données non issues des **sorties structurées** du snapshot (extraction + digest).

---

#### Principe général

Toute URL manipulée par le pipeline (produit source, candidat comparable, offre, page SERP) suit le cycle suivant :

1. **Capture de la page**
2. **Extraction structurée**
3. **Production d’un digest déterministe**
4. **Persistance immuable**
5. **Traçabilité via `tool_runs`**


Ce cycle est identique quel que soit le provider utilisé.

Providers supportés (et équivalents fonctionnels pour le module snapshot) :
- **Playwright MCP** : navigateur contrôlé (rendu JS complet), adapté aux pages dynamiques et aux contenus chargés côté client.
- **Browserbase** : navigateur hébergé (rendu JS complet) utilisé quand l’exécution doit être externalisée (isolement, capacité, contraintes réseau).
- **HTTP simple / crawler SERP** : capture rapide pour pages statiques ou lorsque le rendu navigateur n’apporte pas de valeur.

La sélection du provider est **une décision d’exécution** (performance / robustesse / coût) qui ne change pas le contrat : la sortie reste un `PageSnapshotResult` traçable et rejouable.

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
- Toute décision métier consomme uniquement les **sorties structurées** (extraction + digest) ; aucune dépendance au HTML brut par défaut.
- Le **reprocessing** est garanti à partir des données structurées persistées ; la preuve brute n’est requise que si le mode debug/audit est activé.
- Le LLM n’a **jamais accès direct au HTML brut** : il ne consomme que des données structurées issues du snapshot.

- Par défaut, le snapshot conserve : **URL finale**, horodatage, provider, statut, extraction_method/status, extracted_json, digest_json, digest_hash. La preuve brute (HTML/screenshot/HAR) est **optionnelle** et activée uniquement en debug/audit.

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

	•	Tous les providers (Playwright MCP, Browserbase, HTTP simple, crawler SERP) utilisent ce module.
	•	Les phases du pipeline (source_snapshot_capture, candidate_snapshot_capture, offers_recall_and_fetch) ne manipulent jamais de contenu web non snapshoté.
	•	La base produit interne est dérivée exclusivement de snapshots validés.

Le snapshot est ainsi le socle factuel, auditable et durable sur lequel repose l’ensemble du système.

## 6.4 Frugalité

- Les artefacts lourds sont stockés uniquement s’ils ont une valeur métier.
- Les runs non critiques peuvent être purgés après une durée limitée.
- Un mode debug/audit renforcé peut être activé explicitement.
- Les preuves brutes (HTML/screenshot/HAR) sont conservées sous TTL court et/ou uniquement pour les runs promus, afin de limiter le stockage ; le fonctionnement nominal repose sur extraction + digest.

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

---

## 10. Webapps, accès et rôles

### 10.1 Trois webapps (vues) sur un backend unique

Le système expose **trois webapps distinctes** (front-ends) qui consomment la **même API** et les **mêmes modules métier** :

- **Webapp Public (production-like)** : parcours utilisateur (demande, validation, suivi) sans outils internes.
- **Webapp Ops (interne)** : traitement opérationnel (exceptions, suivi, messages, gestion transverse).
- **Webapp Debug (outils)** : exploration technique, tests isolés des services (snapshot, extraction, providers, runs, artefacts debug).

Ces webapps **ne sont pas** des modules métier : elles sont des **clients**. La logique métier reste exclusivement dans les modules (ex. `discovery_compare`, `snapshot`, puis `ordering`, `fulfillment_tracking`, etc.).

### 10.2 Modes d’accès et principe “anonyme → identifié”

Le système distingue :

- un **mode d’accès** : `anonymous` vs `authenticated`,
- des **rôles** (une fois authentifié).

Principe directeur (centrale d’achat publique) :

- tout ce qui est **exploratoire** (recherche, comparaison, constitution d’un brouillon) peut être **anonyme**,
- tout ce qui déclenche un **circuit de validation** doit être **identifié**,
- tout ce qui est **engageant** (envoi Chorus Pro, déclenchement de commande) doit être **identifié** et porté par le rôle adéquat.

### 10.3 Rôles fonctionnels

#### Rôles côté utilisateurs (clients)

- **Demandeur (`requester`)** : prépare un panier, complète les informations, soumet une demande de validation.
- **Valideur (`approver`)** : approuve/refuse une demande et déclenche l’acte engageant (envoi Chorus Pro, commande).

#### Rôles internes

- **Ops (`ops`)** : traitement des exceptions, suivi d’exécution, corrections administratives, messages.
- **Debug / Admin technique (`debug`)** : accès aux endpoints et outils de debug (snapshots, tool_runs, llm_runs, tests providers).

### 10.4 Zoning API (frontières d’exposition)

La séparation des zones d’accès doit exister **dès le départ** dans le routing API, même si l’IAM final (SSO, gestion fine) est reporté.

Recommandation de zoning :

- `/v1/public/*` : accès **libre/anonyme** (aucune action engageante).
- `/v1/app/*` : accès **authentifié** (rôles `requester`/`approver`).
- `/v1/ops/*` : accès **interne** (`ops`).
- `/v1/debug/*` : accès **technique** (`debug`).

Les endpoints de debug sont considérés sensibles par défaut et ne doivent jamais être exposés dans la webapp Public.

### 10.5 Panier “draft” anonyme persistant (avant soumission)

Objectif : permettre une navigation fluide et robuste (refresh, retour arrière, reprise) **sans authentification** jusqu’à la soumission.

Stratégie :

- création d’un **draft de panier** persistant côté serveur,
- rattachement au `anonymous_session_id` (cookie),
- contrôle d’accès par possession de session (éviter l’énumération : réponses 404 en cas de non-possession),
- bascule vers l’identifié au moment de `submit_for_approval` (claim).

Pour garantir le **retour arrière**, le draft est **versionné** (append-only) ou journalisé de façon déterministe : le “retour” sélectionne une version antérieure plutôt que de dépendre de l’historique navigateur.

### 10.6 Soumission et validation (procédure)

- **Soumission** : action réservée à un utilisateur authentifié (`requester`). Elle fige une version soumise du panier (immutabilité/versioning strict).
- **Validation** : action réservée au rôle `approver` ; elle déclenche les actes engageants (envoi Chorus Pro, création/activation d’une commande).

La validation porte explicitement sur une **version** du panier afin de garantir l’audit : qui, quand, quelle version.

### 10.7 Historique des recherches (anonyme puis revendicable)

L’historique des recherches est un journal UX (append-only) reliant une session (anonyme) ou un utilisateur (authentifié) à des runs (ex. `compare_runs`).

- En mode **anonyme** : l’historique est rattaché au `anonymous_session_id`.
- Après authentification : l’historique peut être **claim** (rattaché à `owner_user_id`) sans perdre la continuité UX.

L’historique ne duplique pas les artefacts : il référence les `run_id` et conserve un **résumé minimal** destiné aux listes (URL source, timestamp, statut, quelques champs synthétiques).

### 10.8 Stratégie IAM : tôt mais minimal

Le système doit mettre en place **tôt** une ossature AuthN/AuthZ (modes + rôles + guards) afin de pouvoir développer la webapp Debug sans risque d’exposition.

En revanche, les choix et raffinements suivants peuvent être reportés : fournisseur SSO, gestion fine des permissions, administration complète des comptes.

---
## 11. Webapp Debug — Doctrine et objectifs

La **webapp Debug** est un outil **interne, non orienté utilisateur final**, destiné à :

- tester chaque service du backend **isolément**,
- diagnostiquer non seulement *si* ça fonctionne, mais *si ça fonctionne bien*,
- analyser la qualité des propositions (Exa, LLM, ranking),
- auditer la méthode (prompts, schémas, fallbacks, décisions),
- fournir des artefacts **copiables** pour investigation, support ou analyse LLM (ChatGPT).

Cette webapp est un **outil de vérité opérationnelle** : elle expose les faits, les décisions, les erreurs et les incertitudes, sans tentative de les masquer.

### 11.1 Principes UI/UX transverses (normatifs)

#### Double représentation systématique

Toute information exposée par la webapp Debug existe sous deux formes complémentaires :

1. **Vue condensée (par défaut)**  
   - lisible par un humain,
   - focalisée sur les signaux utiles,
   - sans verbosité excessive.

2. **Vue brute (foldable)**  
   - JSON exact tel que stocké ou reçu,
   - aucune transformation ni enrichissement,
   - lisibilité non prioritaire,
   - toujours accompagnée d’un bouton **copier**.

Le JSON brut **n’est jamais affiché par défaut**.

---

#### Gestion des erreurs (priorité absolue)

- Toute erreur doit être **visible sans scroll**.
- Les erreurs sont classées explicitement :
  - `error` (échec bloquant),
  - `warning` (fallback, partial, indeterminate),
  - `ok`.

Chaque erreur expose :
- son type (API, provider, validation, timeout, schéma…),
- un message court,
- la phase concernée,
- un bouton **📋 Copier erreur brute** (JSON complet, même illisible).

La lisibilité n’est pas un objectif pour les erreurs ; la **copiabilité** l’est.

---

#### Mode “Copier pour ChatGPT”

Chaque page (ou run) expose un bouton :

> **📋 Copier résumé debug**

Ce résumé est :
- textuel,
- structuré,
- volontairement condensé,
- limité aux informations pertinentes :
  - erreurs et warnings,
  - décisions clés,
  - paramètres effectifs,
  - identifiants (run_id, snapshot_id, llm_run_id).

Aucun JSON brut n’y figure afin de rester exploitable dans un contexte LLM.

---

### 11.2 Surfaces Debug (pages) et services testés

La webapp Debug est organisée autour de **surfaces** dédiées à des services métiers testables. Chaque surface doit permettre d’évaluer la **qualité** (cohérence, stabilité, pertinence), pas uniquement le statut “OK”.

#### 1) Run Explorer (liste + détail + diff)

**Objectif** : comprendre rapidement *ce qui s’est passé* lors d’un run complet.

Doit permettre :
- liste filtrable des runs,
- vue détaillée (résumé condensé + timeline des phases),
- navigation vers snapshots / tool_runs / llm_runs / prompts,
- comparaison entre deux runs (diff ciblé : phases, erreurs, outputs clés, temps).

#### 2) Snapshot Inspector (URL → extraction/digest/fallback)

**Objectif** : vérifier capture, extraction, digest et ladder de fallback.

Doit permettre :
- inspection par URL et par snapshot_id,
- affichage clair extraction vs digest (vue condensée),
- exposition explicite des `missing_critical` et erreurs,
- accès foldable aux JSON bruts (extracted_json, digest_json, errors_json).

#### 3) Recall Lab (Exa) — requêtes, résultats, annotation

**Objectif** : juger la pertinence des propositions Exa et diagnostiquer les biais (bruit, mono-domaine, manque de précision).

Doit permettre :
- exécuter un recall (paramètres visibles),
- afficher top N (titre, domaine, score, snippet),
- annoter manuellement (pertinent / non pertinent + raison),
- exposer requête envoyée et réponse brute Exa (foldable).

#### 4) Candidate Judge (comparabilité, ranking, breakdown)

**Objectif** : auditer la décision de comparabilité et le ranking déterministe.

Doit permettre :
- verdict explicite (yes/no/indeterminate),
- score global + breakdown (comparability, coverage, identity_strength),
- reasons_short et signals_used,
- comparaison interactive entre candidats.

#### 5) LLM Runs (prompt/schema/output/validation)

**Objectif** : vérifier que le LLM est encadré correctement (facts-first, json-schema strict, validation réelle) et que les erreurs sont exploitables.

Doit permettre :
- liste des llm_runs par phase,
- vue détaillée : prompt, json-schema, input, output, validation_errors,
- copier chaque section (dont prompt) et exposer les erreurs sans souci de lisibilité.

#### 6) Golden Set Runner (batch + score qualité)

**Objectif** : mesurer la qualité globale sur un corpus de référence (stabilité, taux d’erreur, taux d’indeterminate, qualité de recall).

Doit permettre :
- exécuter un batch sur un set d’URLs,
- afficher KPIs agrégés (extraction_method, erreurs, indeterminate, latence),
- drill-down vers chaque run.

---

### 11.3 Positionnement stratégique

La webapp Debug n’est pas :
- une interface utilisateur finale,
- un outil de démonstration,
- un simple “ça marche / ça ne marche pas”.

C’est un **outil d’ingénierie, d’audit et de vérité**, pilier de :
- la **fairness procédurale**,
- la **traçabilité**,
- la maîtrise du **non-déterminisme**,
- l’amélioration itérative de la qualité (providers, prompts, règles, ranking).