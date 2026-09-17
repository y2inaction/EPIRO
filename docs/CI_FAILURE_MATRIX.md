# EPIRO — CI Failure Matrix

Required by master build spec §67. Every CI failure is recorded here with its exact error, root cause, fix and verification, so that the same failure is never diagnosed twice.

**Rule:** append a row on every CI failure. A row is only complete when *Root cause* names the actual defect — not the symptom, and not "suppressed".

---

## Legend

| Column | Meaning |
|---|---|
| **Root cause** | The underlying defect. If a fix suppressed a symptom instead of correcting a cause, this column says so and the row is flagged `DEBT`. |
| **Verification** | How the fix was confirmed. `CI` = observed green in a subsequent run. |

---

## Historical failures (runs #24 – #31, branch `claude/beautiful-fermi-npx5r9`)

| # | Job | Command | Error | Root cause | Fix | Verification | Commit |
|---|---|---|---|---|---|---|---|
| 1 | Lint and Format Check | `isort --check-only app/` | `UnsupportedSettings: allow_separated_trailing_comma` | Invalid key in `[tool.isort]`; the setting does not exist in isort 5.x | Removed the key from `pyproject.toml` | CI | `069e1c1` |
| 2 | Lint and Format Check | `isort --check-only app/` | Import-order mismatch between local and CI results | Version skew — isort 5.13.2 pinned in `requirements.txt`, 9.0.1 installed locally | Aligned to the pinned CI version | CI | `2bd9920` |
| 3 | Lint and Format Check | `black --check app/` | Line-length and formatting diffs across multiple files | Competing Black configuration between `/pyproject.toml` and `/apps/api/pyproject.toml` (see `REBUILD_AUDIT.md` §8.3) — the root config was never loaded | Reformatted source to satisfy the config CI actually loads | CI | `829ecb6`, `0feb097`, `7566ac6`, `24950cb`, `217b5dc`, `e4f1cd1` |
| 4 | Test Backend | `pytest tests/` | `InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API` | `metadata` is reserved by SQLAlchemy's declarative base; used as a column name on 7 models | Renamed all occurrences to `metadata_json` | CI | `c8659ec` |
| 5 | Type Check | `mypy app/ --ignore-missing-imports` | `Generator` used without type parameters | Missing type arguments on `get_db` return annotation | Annotated as `Generator[Session, None, None]` | CI | `08f7dbc` |
| 6 | Test Frontend | `npm run type-check` | `TS5023: Unknown compiler option 'always'` | Invalid key in `tsconfig.json` | Removed the key | CI | `08f7dbc` |
| 7 | Type Check | `mypy app/` | `ImportError: cannot import name 'HTTPAuthCredentials'` | Wrong class name — the FastAPI class is `HTTPAuthorizationCredentials` | Corrected the import | CI | `ccbe5a3` |
| 8 | Type Check | `mypy app/` | Name collision on `status` in `api/evidence.py` | Query parameter named `status` shadowed the imported `fastapi.status` module | Renamed the parameter to `evidence_status` | CI | `ccbe5a3` |
| 9 | Type Check | `mypy app/` | Numerous ORM attribute errors across models, repositories and routers | **Legacy SQLAlchemy 1.x `Column(...)` declarations are not type-checkable.** The correct fix is migration to 2.x `Mapped[T]` / `mapped_column(...)` | ⚠️ **Suppressed**, not fixed — `# type: ignore` then `# mypy: ignore-errors` added to 9 modules | CI (green, but the job now validates nothing) | `ccbe5a3`, `3195408` |
| 10 | Security Scan | `github/codeql-action/upload-sarif@v3` | `Resource not accessible by integration` | Job lacked `security-events: write` | Added job-level permission | CI (error changed — see #11) | `991a25b` |
| 11 | Security Scan | `github/codeql-action/upload-sarif@v3` | `Resource not accessible by integration` (persisted) | Also required `actions: read` for the CodeQL Action API endpoints | Added `actions: read` | CI (error changed — see #12) | `077c0cc` |
| 12 | Security Scan | `github/codeql-action/upload-sarif@v3` | `Code scanning is not enabled for this repository. Please enable code scanning in the repository settings.` | **External repository setting.** Trivy runs successfully and produces valid SARIF; only the upload is refused. Workflow permissions are correct and minimal | ⛔ **Unresolved — requires repository owner action:** enable Code Scanning under *Settings → Code security and analysis* | Pending | — |

---

## Phase 1 findings

Defects found while rebuilding, recorded here because each would have become a
CI failure the moment a real test exercised the code.

| # | Job | Command | Error | Root cause | Fix | Verification | Commit |
|---|---|---|---|---|---|---|---|
| 13 | Test Backend | `pytest tests/` | `ValueError: password cannot be longer than 72 bytes` from `hash_password` | `bcrypt` was never pinned, so pip installed 5.x. passlib 1.7.4 probes its bcrypt backend with an over-length password; bcrypt ≥ 4.1 removed `__about__` and 5.x raises instead of truncating, so **every** call failed. Registration and login were broken in any fresh install | Pinned `bcrypt==4.0.1`. The old test suite could not detect this because no test ever hashed a password | Local test suite, then CI | `0823a41` |
| 14 | Type Check | `mypy app/` | 41 errors on removing the `# mypy: ignore-errors` directives | Legacy SQLAlchemy 1.x `Column()` declarations are not checkable, so the suppressions were hiding genuine defects: `str` path parameters passed to `UUID` columns, a string assigned to a datetime column, an untyped heterogeneous dict | Converted the ORM to 2.x `Mapped[T]`/`mapped_column` and fixed each error | `mypy` clean with zero suppressions across 30 files | `706c036` |
| 15 | Lint | `flake8 app/` | 14 findings on widening `--select` | The gate selected only `E9,F63,F7,F82`, which excludes unused imports and variables entirely | Removed the narrowing, added `.flake8`, fixed all 14 | `flake8` clean | `747935c` |
| 16 | — | `alembic upgrade head` | `type "integritysignalpriority" already exists` after a downgrade | Autogenerate's downgrade drops tables but leaves native enum types behind, so re-upgrade fails | Added explicit `DROP TYPE` statements to the downgrade | upgrade → downgrade → upgrade round trip on a fresh database | `347aaa4` |
| 17 | — | `alembic revision --autogenerate` | Proposed `op.drop_table('spatial_ref_sys')` | Autogenerate does not know PostGIS owns that table | Wired GeoAlchemy2's `include_object` into `env.py`, which prevents it for all future migrations rather than just this one | `alembic check` reports no drift | `347aaa4` |

---

## Open technical debt arising from these failures

| Ref | Item | Status |
|---|---|---|
| #9 | `# mypy: ignore-errors` in 9 modules renders the Type Check job vacuous | **Resolved** in `706c036`. Zero suppressions remain |
| #3 | Two competing `pyproject.toml` files; the root `[tool.isort]` and `[tool.mypy]` sections are never loaded by CI | **Resolved** in `747935c`. One authoritative config that CI demonstrably reads |
| #12 | Security Scan cannot pass | **Resolved externally.** Code Scanning was enabled by the repository owner |
| #13 | `passlib` is unmaintained and incompatible with current `bcrypt`, holding the pin at 4.0.1 | Open. Replace passlib with direct `bcrypt` use so the pin can be lifted |

---

## Lessons encoded

Derived from the 19-commit CI-chasing sequence that preceded this audit:

1. **A green job is not a passing job.** Four of the six CI jobs validated almost nothing while reporting success (`REBUILD_AUDIT.md` §8). Verify what a job actually asserts before trusting it.
2. **Confirm the configuration is loaded before editing it.** Ten commits were spent adjusting formatter settings that the CI working directory never read.
3. **Suppression is not a fix.** Row #9 turned a failing signal into a silent one. Spec §41 forbids this, and the audit found the defects it was hiding.
4. **Read the log, change one thing, observe.** Rows #10 → #11 → #12 each produced a *different* error, which is how a permissions problem was correctly separated from a repository-settings problem.
5. **Stop at the boundary.** When the cause is outside the repository (row #12), document it and escalate rather than adding speculative permissions.

---

*Maintained per spec §67. Append on every failure; never delete a row.*
