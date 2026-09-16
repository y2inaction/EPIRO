# EPIRO — Rebuild Audit (Phase 0)

**Audit date:** 2026-09-16
**Branch audited:** `claude/beautiful-fermi-npx5r9` @ `077c0cc`
**Scope:** Entire repository — 70 tracked files, backend, frontend, database, infrastructure, CI/CD, documentation.
**Method:** Direct inspection of every source file, git history, workflow logs from CI runs #24–#31.

> **Status labels used in this document** (per master build spec §81)
> `CONFIRMED` — verified by direct inspection · `BROKEN` — verified defective · `MISSING` — no implementation exists · `[VERIFY]` — needs runtime confirmation

---

## 1. Executive summary

EPIRO currently exists as a **thin architectural sketch, not a working platform**. The repository contains a plausible-looking directory structure, 15 ORM models and 33 route handlers, but the system has three foundational defects that make the current codebase unsafe to build on:

1. **Authorization is effectively absent.** The admin dependency is a no-op, so every "admin only" endpoint is open to any self-registered user. Evidence and public information can be verified, approved and published by anyone with an account. This defeats the platform's central promise.
2. **The test suite is inert.** No test exercises the application. `test_models.py` passes whether or not imports succeed. Green CI has therefore been certifying nothing, which is how the defects above survived 31 CI runs.
3. **The database layer is internally inconsistent.** Migrations cover 2 of 15 tables, disagree with the models on column names, and are bypassed at runtime by `create_all()`. The Postgres init script contains three statements that will error on startup.

The recommendation is **not** to delete the repository. The domain modelling, enum vocabulary, route surface and infrastructure scaffolding are a genuinely useful starting point and should be preserved and corrected. What must be rebuilt is the **governance spine**: authorization, workflow gating, audit, persistence correctness, and the test suite that proves them.

**Estimated distribution of the 89-section specification:** ~12% partially implemented, ~5% implemented correctly, ~83% not started.

---

## 2. Current repository state

### 2.1 Structure

```
EPIRO/
├── apps/api/          FastAPI backend — 28 Python files
│   ├── app/
│   │   ├── api/       8 routers, 33 endpoints
│   │   ├── models/    2 files, 15 models + 2 association tables
│   │   ├── repositories/  3 files
│   │   ├── schemas/   2 files
│   │   └── workers/   1 file (stubs)
│   ├── alembic/       1 migration (incomplete)
│   └── tests/         4 files (no real coverage)
├── apps/web/          Next.js frontend — 2 route files total
├── infrastructure/    nginx + postgres init
├── docs/              1 file (API.md)
└── .github/workflows/ 1 workflow, 6 jobs
```

### 2.2 Git history

30 commits. The last **19 consecutive commits** are CI-chasing changes (formatting, tool config, type suppression, workflow permissions) with no feature content. This is the pattern the master spec §66 exists to stop, and it is the strongest signal that the project needs a controlled reset of method rather than of code.

Notable history markers:
- `c8659ec` renamed the SQLAlchemy reserved `metadata` attribute → `metadata_json` in models **but not in the migration**, creating a permanent schema divergence (see §9.2).
- `3195408` introduced blanket `# mypy: ignore-errors` across 9 modules, which the master spec §41 explicitly forbids.
- `2bd9920`, `069e1c1`, `fdeae94`, `01133f7`, `52bf0f1`, `829ecb6`, `217b5dc`, `e4f1cd1`, `390d699`, `4490b6d` — ten commits fighting formatter/linter configuration that was never being loaded (see §8.3).

### 2.3 Branches

- `main` — stable baseline
- `claude/beautiful-fermi-npx5r9` — active development branch, open as PR #1

No history should be destroyed. Per master spec §86, the existing tree contains preservable work.

---

## 3. What works (CONFIRMED)

These components are correct and should be **preserved** through the rebuild:

| Component | File | Assessment |
|---|---|---|
| Password hashing | `app/security.py:12-22` | bcrypt via passlib, correct construction |
| JWT issue/decode | `app/security.py:25-77` | Timezone-aware expiry, correct exception handling for expired/invalid |
| Health endpoints | `app/api/health.py` | `/health`, `/health/live`, `/health/ready` with real DB probe |
| Domain vocabulary | `app/models/core.py:17-78` | Role, EvidenceStatus, QuestionStatus, IntegritySignalPriority, ReadinessStatus enums map cleanly onto the spec's operating model |
| Entity relationship sketch | `app/models/core.py` | Organisation → Programme → Project → Evidence → Story chain is the right backbone |
| Session management | `app/database.py:19-33` | `get_db` generator with correct `finally: close()` |
| Nginx reverse proxy | `infrastructure/nginx/default.conf` | Upstream routing and proxy headers are correct |
| Repository pattern | `app/repositories/base.py` | Sound structural choice; implementation needs hardening (§7.4) |
| Compose service topology | `docker-compose.yml` | Correct service decomposition with health-gated `depends_on` |

**Frontend:** `apps/web/app/page.tsx` renders correctly and is the only functioning UI. It is a static landing page.

---

## 4. Broken functionality (verified defective)

### 4.1 `S1 — CRITICAL` Admin authorization is a no-op

`app/dependencies.py:63-78`

```python
async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    from app.models import Role          # imported, never used
    if not current_user:                 # get_current_user already raised if falsy
        raise HTTPException(403, ...)
    return current_user                  # every authenticated user passes
```

`get_current_user` either raises or returns a `User`. The guard condition is therefore **unreachable**, and this dependency grants admin to every authenticated account.

**Eight endpoints depend on it and are consequently unguarded:**
- `POST /api/v1/organisations/` — create organisation
- `PUT /api/v1/organisations/{id}` — modify any organisation
- `DELETE /api/v1/organisations/{id}` — **cascade-deletes all programmes, projects, evidence and sources of that organisation**
- `GET /api/v1/organisations/` — enumerate all tenants
- `GET /api/v1/users/` — enumerate all users (email, phone) across all tenants
- `POST /api/v1/users/{id}/deactivate` — disable any account, including administrators
- `POST /api/v1/users/{id}/activate`
- (plus `GET /api/v1/users/` search)

Because `POST /api/v1/auth/register` is **unauthenticated and open** (`app/api/auth.py:32`), an anonymous attacker can self-register and reach all of the above.

### 4.2 `S1 — CRITICAL` Governance workflow has no role gating

Every verification, approval and publication endpoint accepts **any authenticated user**:

| Endpoint | File:line | Missing control |
|---|---|---|
| `POST /evidence/{id}/verify` | `api/evidence.py:136` | No verifier role; no separation of duties |
| `POST /evidence/{id}/approve` | `api/evidence.py:156` | No approver role; **same user may verify then approve** |
| `POST /evidence/{id}/publish` | `api/evidence.py:175` | Only checks `approval_status`, not identity |
| `POST /stories/{id}/publish` | `api/stories.py:126` | **No approval gate whatsoever** — draft → published in one call |
| `POST /stories/{id}/feature` | `api/stories.py:150` | No control |
| `POST /questions/{id}/respond` | `api/questions.py:101` | No control |
| `POST /questions/{id}/approve` | `api/questions.py:129` | No control; self-approval possible |
| `POST /questions/{id}/publish` | `api/questions.py:161` | No control |

This is the most damaging class of defect relative to product intent. The spec's core claim — *"No claim should be treated as verified unless it has source, date, owner, verification status, provenance, approval status"* (§6) and *"Public information cannot be published without required approval"* (§51) — is not enforced anywhere in the codebase.

### 4.3 `S1 — CRITICAL` Mass assignment via untyped request bodies

Four endpoints accept a raw `dict` as the request body, bypassing Pydantic entirely:

- `api/evidence.py:98` — `evidence_update: dict`
- `api/organisations.py:81` — `org_update: dict`
- `api/questions.py:81` — `question_update: dict`
- `api/stories.py:95` — `story_update: dict`

These flow into `BaseRepository.update()` (`repositories/base.py:55-68`), which performs unconditional `setattr` for every supplied key. A caller can therefore set `status`, `verification_status`, `approval_status`, `verified_by`, `approved_by`, `is_published`, `organisation_id`, `created_at` or `id` directly — **bypassing the entire approval workflow in a single PUT**, and re-assigning records across tenants.

### 4.4 `S1 — CRITICAL` No multi-tenant isolation

No endpoint verifies that the caller belongs to the organisation whose data it returns or mutates.

- `api/evidence.py:18` — `organisation_id` is taken from a query parameter and trusted verbatim.
- `api/evidence.py:45` — fetch by ID with no tenant scoping.
- `api/search.py:17` — global search queries Evidence, Story, Question and Project **across all organisations** with no filter.
- `api/questions.py:16` — `organisation_id` is optional; omitting it returns every question in the system.
- `api/stories.py:16` — no scoping possible: **the `Story` model has no `organisation_id` column at all** (`models/core.py:361-383`). Tenant isolation for public information is structurally impossible in the current schema.

The `user_organisation` association table (`models/core.py:82-88`) carries a per-organisation `role`, but **no code ever reads it**.

### 4.5 `S2 — HIGH` Broken authorization logic in user update

`api/users.py:99`

```python
if str(current_user.id) != user_id and not current_user.is_active:
```

`get_current_user` rejects inactive users at `dependencies.py:54`, so `current_user.is_active` is always `True` and the right operand is always `False`. The condition can never fire: **any authenticated user can modify any other user's profile.**

### 4.6 `S2 — HIGH` Postgres init script will fail

`infrastructure/postgres/init.sql` — three defective statements, executed by `docker-entrypoint-initdb.d`:

| Line | Statement | Defect |
|---|---|---|
| 3 | `CREATE EXTENSION IF NOT EXISTS pgvector` | Extension is named `vector`, not `pgvector` |
| 4 | `CREATE EXTENSION IF NOT EXISTS uuid-ossp` | Unquoted hyphenated identifier — **SQL syntax error**; requires `"uuid-ossp"` |
| 7-9 | `ALTER DATABASE epiro SET encoding / lc_collate / lc_ctype` | These are immutable creation-time properties, not runtime settings — rejected by Postgres |

The same wrong extension name recurs in `app/database.py:41` and `alembic/versions/001_initial_schema.py:24`.

**Consequence:** `docker-compose up` does not reach a healthy database. Quality Gates 1 and 2 (§68) currently fail. `[VERIFY]` — worth a single confirming run, but the SQL defects are unambiguous on inspection.

### 4.7 `S2 — HIGH` DDL executed on every database connection

`app/database.py:36-42` registers a `connect` event listener that issues `CREATE EXTENSION` on **every new connection**. Combined with `poolclass=NullPool` (line 15) — which opens a fresh connection per request — this means two DDL statements per HTTP request, and requires the application role to hold superuser privileges in production.

### 4.8 `S2 — HIGH` Response serialization is very likely broken at runtime

Every response schema declares `id: str`, `created_at: str`, `updated_at: str` (`schemas/core.py`, `schemas/auth.py:31-45`), while the ORM supplies `UUID` and `datetime`. Pydantic v2 does not coerce `UUID → str` or `datetime → str` in non-strict mode; it raises `ValidationError`.

Affected: every `*.model_validate(...)` call — login, register, user list, evidence list/get/create/update, story, question, organisation, and all four search result sets. `[VERIFY]` — needs one runtime confirmation, but the type mismatch is definite and there is no test that would have caught it.

### 4.9 `S3 — MEDIUM` Docker image build is never exercised

The CI job named **"Build Docker Images"** (`.github/workflows/ci.yml:147-177`) runs `checkout`, `setup-buildx`, `docker/login-action` (skipped on PRs) and `docker/metadata-action`. **It never invokes a build.** The job reports success without producing or validating an image.

Independently, `apps/web/Dockerfile:14` contains `COPY --from=builder /app/public ./public` — and **no `public/` directory exists in the repository**, so a real build would fail.

### 4.10 `S3 — MEDIUM` Dead frontend navigation

`apps/web/app/page.tsx:18,24` link to `/dashboard` and `/login`. Neither route exists — `apps/web/app/` contains only `page.tsx` and `layout.tsx`. Both links 404.

---

## 5. Incomplete functionality

| Area | Present | Missing |
|---|---|---|
| Evidence registry | Model + 8 endpoints | Permanent human-readable evidence ID (§10); indicator/baseline/target fields; provenance chain; versioning behaviour; WHO/beneficiary entities |
| Source registry | Model + no endpoints | **No API at all**; document hash, reliability classification, reviewer, review/expiry dates (§11) |
| Projects | Model + no endpoints | **No API at all**; milestones, indicators, beneficiaries, field visits, issues (§12) |
| Thematic areas | Model + no endpoints | **No API at all**; admin-configurable taxonomy (§9) |
| Locations | Model + no endpoints | **No API at all**; hierarchy is flat strings, not entities (§13) |
| Integrity signals | Model only | **No API, no workflow, no response clocks** (§18, §19) |
| Readiness scenarios | Model only | **No API, no playbooks, no drills, no dashboard** (§8, §S7) |
| Audit log | Model only | **Never written to by any code path** (§38) |
| Background jobs | 3 stub tasks returning strings | All real processing (§44) |
| Frontend | 1 static page | Everything (§42, §58, §76) |

---

## 6. Completely missing modules

No model, no endpoint, no UI exists for the following required areas:

**Data/domain:** Media asset management (§25) · Stakeholder CRM (§29) · Meetings (§30) · Task management (§31) · Field missions (§16) · Geographic hierarchy entities (§13) · Indicators & milestones (§12) · Translation entities (§28) · Reports (§54)

**Capability:** AI assistant (§32) · RAG / knowledge system (§33) · Document processing & OCR (§34) · Configurable approval engine (§36) · RBAC enforcement (§37) · Notifications (§45) · Analytics (§53) · Import/export (§52) · Admin panel (§57) · Rapid response engine (§19) · National listening network (§20) · Intelligence workspace (§21) · Executive dashboard (§22) · Operating rhythm workflows (§23, §24) · Creative layer (§27) · Offline/grassroots toolkit (§17) · Public hub (§14)

**Cross-cutting:** Information graph (§72) · End-to-end traceability (§73) · Change-impact flagging (§74) · Knowledge versioning (§75) · Demo mode (§55) · Seeding (§56) · Privacy controls (§40) · Design system (§58) · Accessibility (§76)

AI/LLM dependencies are commented out of `requirements.txt:40-45`, so §32 and §33 have neither implementation nor dependencies.

---

## 7. Architectural problems

### 7.1 SQLAlchemy 1.x style in a 2.x codebase

`models/core.py` uses legacy `Column(...)` declarations throughout. The spec (§41) requires `Mapped[T]` / `mapped_column(...)`. The legacy style is the *direct cause* of the type-checking failures that were suppressed rather than fixed — 2.x typed declarations are what make the ORM checkable.

### 7.2 Blanket type suppression

`# mypy: ignore-errors` appears in **9 modules**: `models/core.py`, `repositories/user.py`, `repositories/evidence.py`, `api/auth.py`, `api/users.py`, `api/organisations.py`, `api/evidence.py`, `api/stories.py`, `api/questions.py`, `api/search.py`.

The CI "Type Check" job runs `mypy app/ --ignore-missing-imports` against files that have disabled themselves. **The job is vacuous.** §41 forbids this explicitly.

### 7.3 Dates and money stored as strings/integers

`Column(String)` is used for `start_date`, `end_date`, `evidence_date`, `verified_date`, `approved_date`, `published_date`, `response_date`, `last_login`. This makes range queries, sorting, and time-based intelligence impossible without a data migration.

`budget = Column(Integer)` (`models/core.py:201,232`) has no currency and no decimal precision.

### 7.4 Repository base class defects

`repositories/base.py:55-68` — `update()` skips any field whose value is `None`, so **no field can ever be cleared**; and it applies `setattr` to arbitrary keys with no allow-list (see §4.3).

`get_all()` (line 34) issues an unbounded `COUNT(*)` on every call with no index strategy.

### 7.5 Missing referential integrity

`verified_by`, `approved_by` (Evidence), `assigned_to`, `approved_by` (Question), `assigned_to` (IntegritySignal), `owner` (Scenario) are declared as bare `UUID` columns with **no ForeignKey to `user.id`**. Dangling references are unconstrained.

### 7.6 Structural tenancy gap

`Story`, `Question`, `IntegritySignal`, `Scenario` have inconsistent or absent organisation linkage. `Story` has none. Tenancy must be a modelled invariant, not a query-time convention.

### 7.7 Single global exception handler masks errors

`main.py:75-82` registers a handler for bare `Exception` returning a generic 500. Combined with the absence of request IDs or error tracking (§47), production failures will be undiagnosable.

### 7.8 Unused imports and dead code

`main.py:6` imports `HTTPException` (unused); `dependencies.py:67` imports `Role` (unused); `api/evidence.py:9` imports `Project` (unused); `api/search.py` imports `EvidenceResponse` alongside unused names; `schemas/core.py:3` imports `datetime` (unused); `schemas/core.py:315` defines `PaginatedResponse` which no endpoint uses. The CI lint job cannot catch these — see §8.2.

---

## 8. CI/CD problems

### 8.1 The test suite certifies nothing

`tests/test_health.py` — asserts `True`, `1 + 1 == 2`, and a fixture value. **Does not import or test the health endpoint.**

`tests/test_models.py:19-22`:
```python
except ImportError as e:
    assert "No module named" in str(e) or "cannot import" in str(e)
```
The test **passes when the import fails**. It cannot detect a broken model layer.

`tests/conftest.py` — a single dict fixture. No TestClient, no database fixture, no factories (despite `factory-boy` and `faker` being installed).

**There are zero API tests, zero authentication tests, zero authorization tests.** CI reports "Test Backend ✅" with effectively 0% meaningful coverage of `app/`, and no `--cov-fail-under` gate.

### 8.2 Lint is near-vacuous

`.github/workflows/ci.yml:35`:
```
flake8 app/ --count --select=E9,F63,F7,F82
```
This selects only syntax errors and a few undefined-name checks. Unused imports (F401), unused variables (F841), style and complexity are **all excluded**. The lint job cannot fail on anything short of a syntax error.

### 8.3 Tool configuration is silently inert — root cause of the config churn

There are **two** `pyproject.toml` files:

- `/pyproject.toml` — contains `[tool.black]`, `[tool.isort]`, `[tool.mypy]` and mypy per-module overrides
- `/apps/api/pyproject.toml` — contains only `[tool.black] line-length = 100`

CI runs black, isort and mypy with `working-directory: ./apps/api`. Black and isort resolve the nearest `pyproject.toml` (`apps/api/`) and stop there. Mypy reads config from the **current directory only** and does not walk upward.

**Therefore the entire root `[tool.isort]` and `[tool.mypy]` configuration has never been applied.** The root mypy overrides that set `ignore_errors = false` for `app.models.*` and `app.repositories.*` — the ones that would have countered the inline suppressions — are dead. Ten commits were spent fighting configuration that was never loaded.

The root `[tool.black]` also uses `target-versions` (plural); the correct Black key is `target-version`.

### 8.4 Missing required jobs

Spec §49 requires ten jobs. Present: Lint (weak), Type Check (vacuous), Backend Tests (vacuous), Frontend Tests (trivial), Build (no-op), Security Scan (blocked). **Missing entirely:** Dependency Audit, Integration Tests, and a real Docker Build.

### 8.5 Security Scan — external repository limitation `[DOCUMENTED per Gate 11]`

CI run #31 attempt 2, job 105008845019, step *"Upload Trivy results to GitHub Security tab"*:

```
##[error]Please verify that the necessary features are enabled:
Code scanning is not enabled for this repository.
Please enable code scanning in the repository settings.
```

Trivy itself runs successfully and produces a valid SARIF file. The failure is exclusively at the upload step and is a **GitHub repository-settings limitation, not a code or workflow defect**. Workflow permissions are correct and minimal (`contents: read`, `security-events: write`, `actions: read` — `.github/workflows/ci.yml:182-185`).

**Required external action:** enable Code Scanning under *Settings → Code security and analysis*. Until then, this job cannot pass, and Gate 11 is satisfied by this documented limitation.

### 8.6 CI failure history

Recorded separately in `docs/CI_FAILURE_MATRIX.md` per spec §67.

---

## 9. Database problems

### 9.1 Migrations cover 2 of 15 tables

`alembic/versions/001_initial_schema.py` creates only `organisation` and `user`. **Thirteen tables have no migration:** `thematic_area`, `programme`, `project`, `location`, `source`, `evidence`, `story`, `question`, `integrity_signal`, `scenario`, `audit_log`, plus association tables `user_organisation` and `programme_thematic`.

### 9.2 Migrations disagree with models

`001_initial_schema.py:38` creates a column named `metadata`. The model (`models/core.py:111`) declares `metadata_json`. A database built by Alembic and a database built by `create_all()` have **different schemas**. This divergence is already latent in any environment that has been provisioned.

The migration also omits `server_default` for `created_at`/`updated_at` while declaring them `NOT NULL`, whereas the model sets `server_default=func.now()`.

### 9.3 Migrations are bypassed at runtime

`main.py:35` calls `Base.metadata.create_all(bind=engine)` on every startup. This silently creates the full model schema regardless of migration state, making Alembic decorative. Spec §43 requires that every schema change go through a migration.

### 9.4 Extension name errors

`pgvector` (correct name: `vector`) appears in `database.py:41`, `001_initial_schema.py:24` and `init.sql:3`. `pgvector==0.2.1` is installed but **no vector column exists anywhere in the models**.

### 9.5 No indexes for the actual query patterns

Search uses `ILIKE '%term%'` (`api/search.py`, `repositories/evidence.py:73-76`) across four tables. Leading-wildcard `ILIKE` cannot use a B-tree index; these are guaranteed sequential scans. No trigram or full-text index exists. Spec §35 requires real search.

### 9.6 No soft deletion

`DELETE /evidence/{id}`, `/stories/{id}`, `/organisations/{id}` perform hard deletes with cascade. There is no recovery path and no audit record. Spec §43 requires soft deletion where justified; for an evidence registry it is mandatory.

---

## 10. Security concerns (consolidated)

| # | Severity | Finding | Location |
|---|---|---|---|
| 1 | **Critical** | Admin dependency grants admin to every authenticated user | `dependencies.py:63-78` |
| 2 | **Critical** | Verify / approve / publish endpoints have no role checks; self-approval possible | 8 endpoints, §4.2 |
| 3 | **Critical** | Mass assignment via raw `dict` bodies bypasses all workflow state | 4 endpoints, §4.3 |
| 4 | **Critical** | No multi-tenant isolation on any read or write path | §4.4 |
| 5 | **Critical** | Open unauthenticated registration reaches all of the above | `api/auth.py:32` |
| 6 | **High** | `secret_key` defaults to `"change-me-in-production"` with no production guard — JWTs forgeable if env unset | `config.py:24`, `docker-compose.yml` |
| 7 | **High** | Any user can modify any other user's profile | `api/users.py:99` |
| 8 | **High** | Any user can deactivate any account, including admins | `api/users.py:118` |
| 9 | **High** | Any user can delete an organisation, cascading to all its evidence | `api/organisations.py:103` |
| 10 | **High** | PII (email, phone) of all users exposed to any authenticated caller | `api/users.py:44,69` |
| 11 | **High** | No rate limiting anywhere — login is brute-forceable, public question endpoint is spammable | codebase-wide |
| 12 | **High** | Audit log model exists but **is never written** — no accountability record | `models/core.py:451` |
| 13 | **Medium** | `logout` is a no-op returning success; no token revocation or rotation | `api/auth.py:151` |
| 14 | **Medium** | No `.dockerignore` anywhere; `COPY . .` can copy `.env` into images | `apps/api/Dockerfile:17` |
| 15 | **Medium** | Dev tooling (black, flake8, mypy, pytest) ships in the production image | `requirements.txt:61-66` |
| 16 | **Medium** | Two JWT libraries installed (`python-jose` + `PyJWT`); only PyJWT used | `requirements.txt:18,21` |
| 17 | **Medium** | No security headers (HSTS, CSP, X-Content-Type-Options); nginx exposes 443 with no TLS config | `nginx/default.conf` |
| 18 | **Medium** | Application requires superuser DB privileges to run (`CREATE EXTENSION` per connection) | `database.py:36-42` |
| 19 | **Low** | Redis has no authentication | `docker-compose.yml` |
| 20 | **Low** | `last_login` never recorded despite the column existing | `models/core.py:141` |

**Documentation actively misstates the security posture.** `IMPLEMENTATION_SUMMARY.md:259-276` claims "✅ Authentication on protected endpoints", "✅ Audit logging", "✅ Rate limiting ready", "✅ Input validation throughout". Findings 1–4, 11 and 12 contradict all four claims.

---

## 11. Duplicate functionality

| Duplication | Locations | Resolution |
|---|---|---|
| Two `pyproject.toml` with competing tool config | `/pyproject.toml`, `/apps/api/pyproject.toml` | Consolidate to one authoritative location that CI actually loads |
| Two JWT libraries | `python-jose[cryptography]`, `PyJWT` | Keep PyJWT; drop python-jose |
| Two schema-creation mechanisms | Alembic + `create_all()` | Alembic only |
| Extension creation in three places | `init.sql`, `database.py`, migration `001` | Migration only |
| Pagination block re-implemented per endpoint | 5 routers | Single shared paginator; `PaginatedResponse` already exists unused |
| Ad-hoc filter loops duplicating `BaseRepository.filter` | `api/stories.py:31-37` | Use the repository |
| Search logic in both `search.py` and `repositories/evidence.py` | 2 files | Single search service |
| Dev override duplicates base compose commands | `docker-compose.dev.yml` | Base should be production-shaped; dev overrides only deltas |

---

## 12. Documentation gaps

**Present:** `README.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_SUMMARY.md`, `QUICKSTART.md`, `docs/API.md`

**Required by §60 — 24 of 25 files missing.** Only `docs/API.md` exists. Missing: `ARCHITECTURE.md` (in docs/), `PRODUCT_REQUIREMENTS.md`, `DOMAIN_MODEL.md`, `DATABASE.md`, `SECURITY.md`, `PRIVACY.md`, `AI_GOVERNANCE.md`, `DATA_GOVERNANCE.md`, `DEPLOYMENT.md`, `DEVELOPMENT.md`, `TESTING.md`, `CI_CD.md`, `OPERATIONS.md`, `FIELD_OPERATIONS.md`, `INFORMATION_INTEGRITY.md`, `INTELLIGENCE_MODEL.md`, `READINESS_MODEL.md`, `CONTENT_WORKFLOW.md`, `APPROVAL_WORKFLOW.md`, `MULTILINGUAL.md`, `SEARCH.md`, `CHANGELOG.md`, `ROADMAP.md` (+ this audit, now created).

**Required by §61 — missing root files:** `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.dockerignore`, `docker-compose.prod.yml`, `Makefile`.

**Accuracy problems (§62, §81):** `IMPLEMENTATION_SUMMARY.md` declares "Production Ready Foundation", "Phase 1 & 2 Complete", "33 fully implemented endpoints" and "100+ documentation files" (there are 5). These claims are not supportable and must be corrected — the spec forbids presenting planned or defective functionality as delivered.

`README.md` documents pgAdmin and a React Query state layer; React Query is installed but unused, and the package pinned (`react-query@3`) is the deprecated predecessor of `@tanstack/react-query`.

---

## 13. Technical debt register

| Item | Cost of delay |
|---|---|
| 9 modules with `# mypy: ignore-errors` | Type checking provides zero signal until removed |
| Legacy SQLAlchemy 1.x declarations | Blocks removal of the suppressions above |
| Dates as strings | Every time-based feature (§21 trends, §53 analytics, §19 clocks) is blocked |
| No test infrastructure | Every subsequent change is unverifiable |
| Inert tool config | Any future formatting dispute repeats the 10-commit cycle |
| Unused dependencies (`python-jose`, `pgvector`, `react-query`, `zustand`, `recharts`, `cva`) | Dependency-audit noise and image bloat |
| Dev deps in production requirements | Larger attack surface in every deployed image |
| Frontend has no API client | All UI work blocked until it exists |
| No seed/demo data | No way to demonstrate or manually test any workflow |

---

## 14. Migration risks

These must be handled deliberately during the rebuild:

1. **`metadata` vs `metadata_json` divergence (§9.2).** Environments provisioned via Alembic and via `create_all()` have different column names. A reconciling baseline migration must detect and normalise both cases rather than assuming either.
2. **Removing `create_all()`.** Any environment currently relying on it has an unversioned schema. Requires an `alembic stamp` path for existing databases.
3. **String → Date/DateTime conversion.** Existing values are unvalidated free text. Needs a conversion migration with an explicit quarantine strategy for unparseable values, not a silent `NULL`.
4. **Adding `organisation_id` to `Story`.** Requires backfill via `evidence.organisation_id` before the `NOT NULL` constraint can be applied.
5. **Introducing real foreign keys** on `verified_by`, `approved_by`, `assigned_to`, `owner` requires cleaning dangling UUIDs first, or the constraint creation fails.
6. **Postgres enum alterations.** `SQLEnum` types are materialised as native enums; adding or renaming values requires `ALTER TYPE` migrations, not model edits.
7. **Hard deletes are unrecoverable today.** Introduce soft deletion *before* any data-cleaning migration, so mistakes are reversible.
8. **`budget` Integer → Numeric** requires a precision decision and currency column; naive casting loses meaning.

---

## 15. Recommended rebuild sequence

The master spec's phase order is sound, with **one deviation**: security and test infrastructure must precede all feature work. Building §14–§35 on the authorization defects in §4 would multiply the blast radius of every finding above.

### Phase 1 — Foundation & governance spine `← start here`
Correct tooling configuration so CI signals are real (§8.3); replace the inert test suite with a working fixture stack (TestClient, transactional DB fixture, factories); convert models to SQLAlchemy 2.x typed declarations and **remove all 9 `# mypy: ignore-errors` directives**; implement real RBAC reading `user_organisation.role`; fix `get_current_admin_user`; add tenant scoping as an enforced invariant; replace the four `dict` bodies with Pydantic schemas and field allow-lists; add audit-log writes on every state transition; fix the Postgres init script and extension names; make Alembic authoritative and write the missing 13 tables; add rate limiting and a production `secret_key` guard.

**Gate:** application starts · migrations apply cleanly · health check green · authentication works · authorization tests prove tenant isolation and role enforcement · lint/format/type checks meaningful and passing.

### Phase 2 — Core evidence
Evidence registry completion (permanent evidence ID, provenance, versioning), Source registry API, Project/Programme API, geographic hierarchy as entities, verification and approval as a configurable workflow engine (§36), real search indexes.

### Phase 3 — Public information
Story engine with enforced approval gating, media library, public portal, public question workflow, multilingual architecture.

### Phase 4 — Field operations
Field missions, offline PWA, capture and synchronisation.

### Phase 5 — Intelligence · Phase 6 — Information integrity · Phase 7 — Readiness
Per spec §69, each behind its own quality gate.

### Phase 8 — AI & knowledge
Document processing, RAG with mandatory citations, AI governance per §32 — grounded, source-linked, never self-certifying verification.

### Phase 9 — Executive system · Phase 10 — Production hardening

### Cross-cutting, every phase
Documentation updated in the same commit as the code it describes; `docs/CI_FAILURE_MATRIX.md` appended on every CI failure; no suppression used as a substitute for a fix.

---

## 16. What to preserve, refactor, rebuild

| Verdict | Items |
|---|---|
| **Preserve** | Domain enums and vocabulary · entity relationship backbone · `security.py` hashing and JWT primitives · health endpoints · nginx routing · compose service topology · repository pattern (as a pattern) · route surface as an API design sketch |
| **Refactor** | `models/core.py` → SQLAlchemy 2.x typed, real FKs, proper date/numeric types · `repositories/base.py` → safe update with allow-lists · response schemas → correct types · Dockerfiles → multi-stage, `.dockerignore` · compose → production-shaped base with dev overrides |
| **Rebuild** | `dependencies.py` authorization · all 8 workflow-transition endpoints · the entire test suite · Alembic migration set · `init.sql` · CI workflow · the frontend (beyond the landing page) · `IMPLEMENTATION_SUMMARY.md` (or delete — its claims are not recoverable) |
| **Do not delete** | Git history, `main`, or the existing branch (§86) |

---

## 17. Answers to the ten required audit questions (§88)

1. **What exists** — A FastAPI backend with 15 models and 33 endpoints, a single-page Next.js frontend, Docker/nginx scaffolding, one partial migration, and an inert test suite.
2. **What works** — Password hashing, JWT primitives, health endpoints, domain vocabulary, service topology, and the static landing page. See §3.
3. **What is broken** — Authorization (critically), workflow gating, tenant isolation, request validation on four endpoints, the Postgres init script, response serialization, the Docker build job, and frontend navigation. See §4.
4. **What should be preserved** — Domain model backbone, enums, security primitives, health checks, infrastructure topology, git history. See §16.
5. **What should be refactored** — ORM declarations to 2.x, repository update safety, response schemas, Dockerfiles, compose layering. See §16.
6. **What should be rebuilt** — Authorization layer, all workflow transitions, the test suite, the migration set, CI, and the frontend. See §16.
7. **What dependencies exist** — FastAPI 0.104.1, SQLAlchemy 2.0.23, Pydantic 2.5.0, Alembic, PostGIS, Redis/Celery, Next.js 14, Tailwind. Unused: `python-jose`, `pgvector`, `react-query`, `zustand`, `recharts`, `class-variance-authority`. AI/LLM dependencies are commented out. Dev tooling incorrectly ships in production requirements.
8. **What CI/CD currently does** — Six jobs. Five pass; four of those five validate almost nothing (lint selects only syntax errors, type check runs against self-suppressed files, backend tests assert `1+1==2`, Docker build never builds). Security Scan fails at SARIF upload due to a repository setting. See §8.
9. **What security configuration exists** — bcrypt hashing and JWT issuance are correctly implemented. Everything above them — authorization, RBAC, tenant isolation, rate limiting, audit logging, secret management — is absent or defective. Twenty findings, five critical. See §10.
10. **Proposed implementation order** — Phase 1 (foundation & governance spine) first, because every later phase inherits the authorization model. Then spec phases 2–10 in order, each behind its quality gate. See §15.

---

## 18. Gate 11 declaration

Per §68, Gate 11 is satisfied as follows: the Security Scan job executes Trivy successfully and generates valid SARIF. The upload step fails because **Code Scanning is not enabled in the GitHub repository settings** — an external repository limitation outside the codebase. Workflow permissions are correct and minimal. This limitation is explicitly documented here and in `docs/CI_FAILURE_MATRIX.md`, and resolves once the repository owner enables Code Scanning under *Settings → Code security and analysis*.

---

*End of Phase 0 audit. No application code was modified in producing this document.*
