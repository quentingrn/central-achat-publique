# Context Snapshot

Date: 2026-01-29

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
- Start: ./scripts/start.sh
- Test: ./scripts/test.sh
- Format: ./scripts/format.sh
- DB migrate: ./scripts/db_migrate.sh
- DB reset: ./scripts/db_reset.sh

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
