# EPIRO documentation

**Start with [STATUS.md](STATUS.md).** It states which spec sections are
built, which are partial and which are untouched. Nothing in this repository
should be described to a stakeholder as working unless STATUS.md marks it
CONFIRMED. If another document here contradicts it, STATUS.md is right and the
other one is stale.

| Document | Covers |
|---|---|
| [STATUS.md](STATUS.md) | What is built, what is partial, what is not started |
| [DOMAIN_MODEL.md](DOMAIN_MODEL.md) | The 19 tables, how they relate, and the conventions behind them |
| [SECURITY.md](SECURITY.md) | Authentication, RBAC, tenancy, separation of duties — and what is *not* enforced |
| [PRIVACY.md](PRIVACY.md) | What is collected about citizens, what is refused, and where the refusals live in code |
| [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) | The evidence, story and question lifecycles, and the approval trail |
| [SEARCH.md](SEARCH.md) | Full-text search, ranking, the eight filters, and the language limitation |
| [API.md](API.md) | Endpoint reference |
| [REBUILD_AUDIT.md](REBUILD_AUDIT.md) | The audit that started this rebuild. A historical snapshot — not current state |
| [CI_FAILURE_MATRIX.md](CI_FAILURE_MATRIX.md) | Every CI failure, its root cause and its fix |

## Still to write

Spec section 60 asks for a larger set. These do not exist yet:
`PRODUCT_REQUIREMENTS.md`, `DATABASE.md`, `AI_GOVERNANCE.md`,
`DATA_GOVERNANCE.md`, `DEPLOYMENT.md`, `DEVELOPMENT.md`, `TESTING.md`,
`CI_CD.md`, `OPERATIONS.md`, `FIELD_OPERATIONS.md`,
`INFORMATION_INTEGRITY.md`, `INTELLIGENCE_MODEL.md`, `READINESS_MODEL.md`,
`CONTENT_WORKFLOW.md`, `MULTILINGUAL.md`, `CHANGELOG.md`, `ROADMAP.md`.

Most of them describe capabilities that are themselves NOT BUILT. Writing them
before the capability exists would produce documentation of something
imaginary, which is the failure mode section 81 is about.
