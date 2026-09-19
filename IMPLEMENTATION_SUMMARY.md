# EPIRO — Implementation Status

**Last updated:** 2026-09-17 · **Branch:** `claude/beautiful-fermi-npx5r9`

> This file previously described the project as a "Production Ready Foundation"
> with "Phase 1 & 2 Complete", "33 fully implemented endpoints", audit logging
> and rate limiting in place. None of that was accurate: the audit in
> `docs/REBUILD_AUDIT.md` found the authorization layer open, the test suite
> inert, and the audit table never written to. It has been rewritten to state
> what is actually built, per the build specification's rule that planned or
> defective functionality must never be presented as delivered.

**Status labels** · `CONFIRMED` verified by a passing test · `PARTIAL` exists
but incomplete · `NOT BUILT` no implementation · `EXTERNAL` depends on
something outside the repository

---

## Where the project actually stands

Phase 0 (audit) and Phase 1 (foundation and governance spine) are complete.
Phases 2–10 have not started. Measured against the 89-section specification,
roughly 15% is implemented and the rest is not yet begun.

This is **not** a production-ready system. It is a correct and tested
foundation on which the feature phases can now be built.

---

## What works — `CONFIRMED`

Each item below is covered by a test that fails if the behaviour regresses.
57 tests, 81% line coverage, enforced by a 75% floor in CI.

### Authentication
- Password hashing (bcrypt) and JWT issue/verify
- Login, registration, token refresh, password change
- Refresh tokens are rejected as access tokens
- Inactive accounts cannot authenticate
- `last_login` is recorded

### Authorization
- Roles are held **per organisation** through `user_organisation`
- `SUPER_ADMIN` confers full rights inside its own organisation only
- Platform administration is a separate `User.is_superuser` flag
- Verify, approve and publish each require their own role
- Separation of duties: one person cannot both verify and approve evidence,
  nor both draft and approve a question response

### Tenant isolation
- Evidence, stories, questions, organisations, users and global search are all
  scoped to organisations the caller belongs to
- A record in another tenant reads as `404`, so ids are not confirmed
- Evidence cannot cite a source owned by another organisation

### Governance gates
- Evidence must be verified before approval, and approved before publication
- A story cannot be published until its supporting evidence is approved
- Workflow state cannot be set through a general update

### Accountability
- Login, and evidence creation, update, deletion, verification, approval and
  publication write to the audit trail
- Deletion captures the record's contents before removal
- Updates capture old and new values

### Platform
- No known vulnerabilities in any runtime or development dependency, enforced
  by a Dependency Audit job running pip-audit and npm audit
- All three Docker images build in CI
- Rate limiting on login and public question submission
- Alembic owns the schema; `alembic check` runs in CI to prevent drift
- Migrations round trip cleanly on a fresh database
- A deployed environment refuses to start with the default or a short signing key
- flake8, black, isort and mypy all pass, with **zero** type suppressions

---

## What exists but is incomplete — `PARTIAL`

| Area | Present | Missing |
|---|---|---|
| Evidence registry | Model, CRUD, workflow | Permanent human-readable ID, provenance chain, versioning |
| Source registry | Model only | No API; document hash, reliability classification, review dates |
| Projects and programmes | Models only | No API; milestones, indicators, beneficiaries |
| Thematic areas | Model only | No API; admin-configurable taxonomy |
| Locations | Model only | No API; hierarchy is flat strings, not entities |
| Integrity signals | Model only | No API, no workflow, no response clocks |
| Readiness scenarios | Model only | No API, no playbooks, no drills |
| Background jobs | Three stub tasks | All real processing |
| Frontend | One static page | Everything; `/dashboard` and `/login` are dead links |

---

## What is not built — `NOT BUILT`

Media asset management · stakeholder CRM · meetings · task management · field
missions and offline PWA · geographic hierarchy · translations · reports · AI
assistant · RAG and knowledge base · document processing and OCR · configurable
approval engine · notifications · analytics · import and export · admin panel ·
rapid response engine · listening network · intelligence workspace · executive
dashboard · operating rhythms · creative layer · public hub · information graph
· traceability and change impact · knowledge versioning · demo data and seeding
· design system · accessibility work

---

## Known limitations

1. **Audit writes are not atomic with the change they describe.** The
   repositories commit their own work, so an audit entry is a second commit.
   Closing this needs the repository layer to stop auto-committing.
2. **`passlib` is unmaintained** and incompatible with current `bcrypt`, so
   `bcrypt` is pinned to 4.0.1. It should be replaced with direct `bcrypt` use.
3. **Rate limit counters are in-process.** A multi-worker deployment needs
   `RATE_LIMIT_STORAGE_URI` pointed at Redis or each worker enforces its own
   allowance.
4. **Deletes are hard deletes.** Soft deletion is not yet implemented; the
   audit trail is currently the only record of what was removed.
5. **Search uses leading-wildcard `ILIKE`**, which cannot use an index. Real
   search indexing is Phase 2 work.
6. **Images are built but not run in CI.** All three now build, but nothing
   starts the stack and exercises it end to end, so a runtime regression in
   the compose topology would not be caught.

---

## Reference

- `docs/REBUILD_AUDIT.md` — full Phase 0 audit, including the 20 security
  findings this phase addressed
- `docs/CI_FAILURE_MATRIX.md` — every CI failure and rebuild defect, with root
  cause and fix
