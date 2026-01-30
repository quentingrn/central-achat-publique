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
- discovery_compare: actif (baseline tables + router HTTP)
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
- page_snapshots: id (uuid), product_id, url, extracted_json (jsonb), created_at, updated_at
- comparable_candidates: id (uuid), product_id, candidate_url, signals_json (jsonb), created_at, updated_at
- offers: id (uuid), product_id, offer_url, price_amount, price_currency, attributes_json (jsonb), created_at, updated_at

## API routes (actuelles + prevues)
- GET /health (actuel)
- POST /v1/discovery/compare (stub 501)

## Commandes utiles (start/test/format/db_reset/db_migrate)
- Start: ./scripts/start.sh (POSTGRES_PORT et API_PORT configurables)
- Test: ./scripts/test.sh
- Format: ./scripts/format.sh
- DB migrate: ./scripts/db_migrate.sh
- DB reset: ./scripts/db_reset.sh
- Prerequis venv: python3 -m venv .venv (scripts utilisent exclusivement .venv/bin/*, PYTHONNOUSERSITE=1)
- Deps test: ./.venv/bin/pip install -e ".[test]"

## Etat des PRs (checklist)
- PR0: structure + qualite OK
- PR1: Postgres + Alembic + baseline migration OK
- PR2: verrous pre-commit/CI OK
- PR3: API + routing + tests OK

## Decisions & Rationale (datees)
- 2026-01-29: Choix PostgreSQL + Alembic (source unique de verite) avec drift guard bloquant par defaut.
- 2026-01-29: UUID pour PK et JSONB pour champs semi-structures.
- 2026-01-29: Scripts CI locaux pour garantir single-head, immutabilite et smoke DB.
- 2026-01-29: Downgrade destructif volontairement bloque dans la baseline (M6).
- 2026-01-29: Nettoyage automatique du port Postgres au demarrage pour eviter "port already allocated"; port configurable via POSTGRES_PORT.
- 2026-01-29: start.sh force un .venv local, attend un healthcheck Postgres avec timeout, et utilise le binaire alembic du venv.
- 2026-01-29: Packaging passe en layout src/ avec Hatchling packages explicites; scripts forcent .venv et PYTHONNOUSERSITE=1 pour eviter les fuites PlatformIO/conda.
- 2026-01-29: Ajout du groupe de dependances [test] (pytest/httpx) et passage du startup FastAPI a lifespan pour supprimer le warning deprecation.
- 2026-01-29: `strategy.md` est réservé à ChatGPT (mise à jour uniquement sur demande explicite de l’utilisateur).
- 2026-01-29: Les stratégies spécifiques par module, si nécessaires, doivent être dérivées de `strategy.md` sans créer de dépendance inverse ni contredire la gouvernance documentaire (statut et périmètre explicités).
