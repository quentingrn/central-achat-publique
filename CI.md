# CI

## Checks
- Single-head Alembic: `./scripts/ci/check_single_head.sh`
- Immutability migrations: `./scripts/ci/check_migrations_immutable.sh`
- DB smoke: `./scripts/ci/db_smoke.sh`

## Exemple pipeline
```bash
./scripts/ci/check_single_head.sh
./scripts/ci/check_migrations_immutable.sh
./scripts/ci/db_smoke.sh
```
