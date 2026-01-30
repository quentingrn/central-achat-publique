# Context Snapshot


## Gouvernance documentaire (normatif)

### Finalité et portée
- `CONTEXT_SNAPSHOT.md` : photographie opérationnelle et vérifiable de l’état du dépôt (référentiel *as-is*).
- `strategy.md` : synthèse stratégique (principes, choix structurants, doctrine) issue des échanges avec ChatGPT.

Ces deux documents ont des rôles complémentaires et non substituables.

### Autorité d’édition
- `CONTEXT_SNAPSHOT.md` ne peut être modifié que par **Codex** (exception ponctuelle : autorisation explicite de l’utilisateur dans ce fil).
- `strategy.md` ne peut être modifié que par **ChatGPT**, et uniquement sur demande explicite de l’utilisateur.

### Règles de production LLM (normatif)
- ChatGPT produit des sorties « copier-coller » :
  - commandes terminal : dans un bloc de code dédié, sans commentaires inline (éviter les erreurs zsh),
  - prompts pour Codex : dans un seul bloc de code, prêts à être copiés-collés.
- Codex commente l’intention (le *pourquoi* / *à quoi ça sert*), pas la mécanique (le *comment*) lorsque le code est déjà auto-explicatif.
- Codex met à jour `CONTEXT_SNAPSHOT.md` à chaque changement significatif (migrations, routes, modèles, scripts, tests) afin de refléter strictement l’état réel du dépôt.

### Obligation de réalité (CONTEXT_SNAPSHOT)
- Toute information déclarée « actuelle » doit être vérifiable dans le dépôt (code, schéma, scripts, tests).
- Interdiction d’indiquer « fait » un élément non présent dans le code.

### Éléments à venir (CONTEXT_SNAPSHOT)
- Les éléments non implémentés sont autorisés uniquement s’ils sont regroupés dans une section dédiée **« À venir / Non implémenté »**.
- Chaque item doit porter un statut explicite : `non implémenté` / `en cours` / `bloqué` / `expérimental` / `abandonné`.
- Aucun élément « à venir » ne doit être mélangé aux sections décrivant l’état réel.

### Nature du contenu (strategy)
- `strategy.md` formalise le « pourquoi / comment » (doctrine, principes, invariants), pas l’état d’avancement.
- Il ne contient pas de checklist d’implémentation ; l’avancement appartient à `CONTEXT_SNAPSHOT.md`.

### Arbitrage en cas de divergence
- `CONTEXT_SNAPSHOT.md` doit être corrigé pour redevenir conforme au code réel.
- `strategy.md` fixe la méthode et les choix structurants, sans se substituer au référentiel d’implémentation.

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
- (à définir)

## Scope & objectifs
- Bootstraper un monolithe modulaire avec FastAPI, SQLAlchemy 2.0, Alembic et PostgreSQL.
- Verrouiller des J0 les regles de migrations (single-head, immutabilite, drift guard, smoke DB).
- Preparer l'integration MCP sans appels reseau obligatoires pour les tests.

## Architecture (diagramme texte)
```
repo/
  apps/api/                -> composition API FastAPI
  modules/*/               -> bounded contexts (domain/application/infrastructure/adapters)
  shared/                  -> kernel, observability, db
  alembic/                 -> migrations (source de verite du schema)
  infra/                   -> docker/db
  scripts/                 -> commandes projet + CI locale
  tests/                   -> unit + integration
```

## Modules & responsabilites (liste + statut)
- discovery_compare: actif (schemas v1 + AgentRunner + comparability gate deterministe + SnapshotProvider Playwright MCP + Exa MCP recall + debug run-centric)
- snapshot: module contract-first (schemas + ports + facade capture_page minimal, non integre)
- ordering: placeholder
- fulfillment_tracking: placeholder
- customer_service: placeholder
- accounts: placeholder
- claims: placeholder

## DB & migrations policy
Regles M1..M6 (normatives):
- M1) Alembic est l'unique source de verite pour le schema.
- M2) Single-head permanent : la branche doit toujours avoir exactement 1 head Alembic. CI echoue sinon.
- M3) Migrations immuables : tout fichier dans alembic/versions/ est immuable apres commit. CI echoue si un fichier existant est modifie/supprime. Seuls les AJOUTS sont autorises.
- M4) CI DB smoke : sur une DB Postgres vierge, executer "alembic upgrade head" puis lancer tests.
- M5) Drift guard : au demarrage API, verifier que la DB est a head ; sinon refuser de demarrer (configurable en dev mais bloquant par defaut).
- M6) Interdiction des migrations destructrices (DROP TABLE/COLUMN) sans justification et plan, a consigner dans CONTEXT_SNAPSHOT.md.

Verrous techniques en place:
- scripts/ci/check_single_head.sh (echoue si >1 head).
- scripts/ci/check_migrations_immutable.sh (echoue si migration existante modifiee/supprimee).
- scripts/ci/db_smoke.sh (upgrade head puis pytest sur Postgres).
- Drift guard dans apps/api/main.py (override via ALLOW_DB_DRIFT=1).

## Schema DB (tables + champs principaux)
- products: id (uuid), brand, model, source_url, created_at, updated_at
- page_snapshots: id (uuid), run_id, product_id, url, final_url, provider, http_status, captured_at, extraction_method, extraction_status, rules_version, content_ref, content_sha256, content_size_bytes, content_type, errors_json, missing_critical_json, digest_hash, extracted_json (jsonb: {digest, extracted, metadata, html_excerpt}), created_at, updated_at
- comparable_candidates: id (uuid), product_id, candidate_url, signals_json (jsonb), created_at, updated_at
- offers: id (uuid), product_id, offer_url, price_amount, price_currency, attributes_json (jsonb), created_at, updated_at
- compare_runs: id (uuid), status, source_url, agent_version, created_at, updated_at
- run_events: id (uuid), run_id, phase_name, status, message, created_at
- prompts: id (uuid), name, version, content, content_hash, created_at
- tool_runs: id (uuid), run_id, tool_name, status, input_json, output_json, created_at
- llm_runs: id (uuid), run_id, prompt_id, prompt_content, prompt_hash, model_name, status, model_params, json_schema, json_schema_hash, input_json, output_json, output_validated_json, validation_errors, created_at

## API routes (actuelles + prevues)
- GET /health (actuel)
- POST /v1/discovery/compare (run complet via stubs, comparability gate deterministe, conforme AgentRunOutputV1)
- GET /v1/debug/compare-runs/{run_id}
- GET /v1/debug/llm-runs/{id}
- GET /v1/debug/tool-runs/{id}
- GET /v1/debug/snapshots/{id}
- GET /v1/debug/prompts/{id}

## Commandes utiles (start/test/format/db_reset/db_migrate)
- Start: ./scripts/start.sh (POSTGRES_PORT et API_PORT configurables)
- Test: ./scripts/test.sh
- Format: ./scripts/format.sh
- DB migrate: ./scripts/db_migrate.sh
- DB reset: ./scripts/db_reset.sh
- Prerequis venv: python3 -m venv .venv (scripts utilisent exclusivement .venv/bin/*, PYTHONNOUSERSITE=1)
- Deps test: ./.venv/bin/pip install -e ".[test]"
- test.sh auto-installe ".[test]" si deps manquantes (venv neuf)
- Env local: .env.local (dev uniquement, jamais committe, ignore via .gitignore)
- Priorite env: process env > .env.local > .env > defaults (settings)
- Env LLM: MISTRAL_API_KEY, MISTRAL_MODEL, DISCOVERY_COMPARE_LLM_ENABLED, DISCOVERY_COMPARE_AGENT_VERSION_MODE, DISCOVERY_COMPARE_LLM_TIMEOUT_SECONDS
- Env Snapshots: DISCOVERY_COMPARE_SNAPSHOT_PROVIDER, DISCOVERY_COMPARE_SNAPSHOT_REQUIRE, PLAYWRIGHT_MCP_MODE, PLAYWRIGHT_MCP_COMMAND, PLAYWRIGHT_MCP_ARGS, PLAYWRIGHT_MCP_CWD, PLAYWRIGHT_MCP_URL, PLAYWRIGHT_MCP_TIMEOUT_SECONDS, PLAYWRIGHT_MCP_INSTALL, DISCOVERY_COMPARE_SNAPSHOT_SCREENSHOT_ENABLED, DISCOVERY_COMPARE_SNAPSHOT_MAX_BYTES, DISCOVERY_COMPARE_SNAPSHOT_USER_AGENT
- Env Exa MCP: DISCOVERY_COMPARE_PRODUCT_CANDIDATE_PROVIDER, EXA_API_KEY, EXA_MCP_URL, EXA_MCP_TIMEOUT_SECONDS, EXA_MCP_LIMIT

## Etat des PRs (checklist)
As-is uniquement : aucune entree "a venir".
- PR0: structure + qualite OK
- PR1: Postgres + Alembic + baseline migration OK
- PR2: verrous pre-commit/CI OK
- PR3: API + routing + tests OK
- PR4: comparability gate deterministe + fairness metrics OK
- PR5: lifecycle LLM + json-schema strict + audit llm_runs OK
- PR6: SnapshotProvider Playwright MCP + extraction deterministe + tool_runs enrichis OK
- PR7: ProductCandidateProvider Exa MCP + tool_runs exa_mcp_recall + tests mockes OK
- PR8: module snapshot (schemas + ports + facade capture_page minimal) OK
- PR9: alignement DB page_snapshots (colonnes snapshot + indexes) OK

## Decisions & Rationale (datees)
- 2026-01-29: Choix PostgreSQL + Alembic (source unique de verite) avec drift guard bloquant par defaut.
- 2026-01-29: UUID pour PK et JSONB pour champs semi-structures.
- 2026-01-29: Scripts CI locaux pour garantir single-head, immutabilite et smoke DB.
- 2026-01-29: Downgrade destructif volontairement bloque dans la baseline (M6).
- 2026-01-29: Nettoyage automatique du port Postgres au demarrage pour eviter "port already allocated"; port configurable via POSTGRES_PORT.
- 2026-01-29: start.sh force un .venv local, attend un healthcheck Postgres avec timeout, et utilise le binaire alembic du venv.
- 2026-01-29: Packaging passe en layout src/ avec Hatchling packages explicites; scripts forcent .venv et PYTHONNOUSERSITE=1 pour eviter les fuites PlatformIO/conda.
- 2026-01-29: Ajout du groupe de dependances [test] (pytest/httpx) et passage du startup FastAPI a lifespan pour supprimer le warning deprecation.
- 2026-01-29: test.sh devient autonome sur venv neuf (auto-install via ".[test]").
- 2026-01-29: Ajout des schemas Pydantic v1 et PhaseNameV1 dans modules/discovery_compare; endpoint stub retourne AgentRunOutputV1 et tests unitaires valident la stabilite des schemas.
- 2026-01-30: Socle debug run-centric ajoute (tables compare_runs/run_events/tool_runs/llm_runs/prompts) + endpoints debug MVP + tests d'integration Postgres.
- 2026-01-30: RunRecorder introduit dans discovery_compare pour ecritures run-centric; tests d'integration marques \"integration\" en pytest.
- 2026-01-30: Ajout des ports providers + stubs deterministes et AgentRunner (9 phases) pour pipeline complet sans reseau.
- 2026-01-30: Comparability gate deterministe (hard-filters + scoring + ranking) et FairnessMetricsV1 calculees; comparability_scoring en tool_run + message d'event.
- 2026-01-30: LLM discipline locale (json-schema strict + validation) + audit complet dans llm_runs; agent_version calcule et persiste dans compare_runs + diagnostics.
- 2026-01-30: SnapshotProvider Playwright MCP (facts-first) avec extraction deterministe JSON-LD + DOM fallback; tool_runs enrichis (requete/response MCP + hashes) et snapshots persistés avec digest/extracted; tests CI utilisent un mock MCP (pas de reseau).
- 2026-01-30: Support Playwright MCP stdio (registry singleton, lazy-init) + start.sh charge .env.local/.env et peut fallback stub si stdio indisponible (opt-in install via PLAYWRIGHT_MCP_INSTALL).
- 2026-01-30: ProductCandidateProvider Exa MCP (requete deterministe, normalisation + dedoublonnage) + tool_run exa_mcp_recall et tests mockes en CI.
- 2026-01-30: Support EXA_API_KEY (query + header) pour Exa MCP HTTP; tool_runs gardent la presence/absence de la cle.
- 2026-01-30: Creation du module snapshot (contract-first) avec facade capture_page minimal et stubs tests, sans integration cross-module.
- 2026-01-30: Alignement DB page_snapshots (colonnes snapshot + indexes digest_hash/run_id/url+captured_at) via migration additive.
- 2026-01-30: Support .env.local (dev only) avec priorite explicite sur .env; .env.local ignore par git et tests unitaires couvrent presence/absence et priorite.
- 2026-01-29: `strategy.md` est réservé à ChatGPT (mise à jour uniquement sur demande explicite de l’utilisateur).
- 2026-01-29: Les stratégies spécifiques par module, si nécessaires, doivent être dérivées de `strategy.md` sans créer de dépendance inverse ni contredire la gouvernance documentaire (statut et périmètre explicités).
