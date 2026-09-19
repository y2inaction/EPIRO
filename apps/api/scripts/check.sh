#!/usr/bin/env bash
#
# Run exactly what CI runs, in the same order, and stop at the first failure.
#
# This exists because of a real failure: a push was verified locally with ruff,
# black and mypy and CI then failed on isort, which nothing local had run. Ruff
# is not in CI at all, and its import-sorting rule is not enabled here, so
# import order was going unchecked while a green local run implied otherwise.
#
# Verifying with a different set of tools than CI uses is not verifying. If a
# command changes in .github/workflows/ci.yml, change it here in the same
# commit — the point of this script is that the two cannot drift.
#
# Usage:
#   scripts/check.sh          # lint, format, imports, types
#   scripts/check.sh --tests  # the above, then the backend suite
#
set -euo pipefail

cd "$(dirname "$0")/.."

# Mirrors the "lint" job in .github/workflows/ci.yml.
echo "==> flake8"
flake8 app/ tests/ --count --show-source --statistics

echo "==> black"
black --check app/ tests/

echo "==> isort"
isort --check-only app/ tests/

# Mirrors the "type-check" job.
echo "==> mypy"
mypy app/

# Mirrors the migration guard in the "test-backend" job. Cheap, and it catches
# the case where a model changed without a migration.
echo "==> alembic check"
alembic check

if [[ "${1:-}" == "--tests" ]]; then
    echo "==> pytest"
    pytest -q
fi

echo
echo "All checks passed."
