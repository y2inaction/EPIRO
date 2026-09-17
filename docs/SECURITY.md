# Security model

Scope: what the API enforces today. Anything not described here is not
enforced — see `docs/STATUS.md` for the distinction between built and planned.

---

## 1. Authentication

JWT bearer tokens, issued at login. Access and refresh tokens are separate
token types and are **not** interchangeable: presenting a refresh token to a
protected endpoint is rejected. This matters because a refresh token has a far
longer life, so accepting one as an access token would silently extend the
window an attacker has after stealing one.

Passwords are hashed with bcrypt. `bcrypt` is pinned to 4.0.1 because
`passlib` 1.7.4 is incompatible with bcrypt 5.x — the pairing fails on every
hash with "password cannot be longer than 72 bytes". The pin has a comment
saying so; do not remove it without replacing passlib.

Login is rate-limited (default 5/minute per address) because it is otherwise
brute-forceable.

## 2. Authorisation

Authorisation is **always** answered against a specific organisation. There is
no global "is admin" question in the codebase except one, described below.

A user holds one role per organisation through the `user_organisation`
association. `AccessControl.require_role(organisation_id, allowed)` asks "what
may this user do *in this organisation*", never "is this user important".

### Role groups

Role sets are named for the operation they authorise rather than for a
hierarchy, so a reader of an endpoint can see what it actually requires:

| Group | Roles | Authorises |
|---|---|---|
| `EVIDENCE_AUTHORS` | researcher, field officer, evidence manager, editor | Creating and editing evidence |
| `EVIDENCE_VERIFIERS` | verifier, evidence manager | Verifying evidence |
| `APPROVERS` | approver, executive | Approving evidence and question answers |
| `STORY_APPROVERS` | approver, executive, editor | Editorial sign-off on a story |
| `PUBLISHERS` | content manager, editor | Releasing approved content |
| `CONTENT_AUTHORS` | content manager, editor, translator | Writing stories |
| `QUESTION_RESPONDERS` | researcher, content manager, editor, evidence manager | Triaging and answering questions |
| `ORG_ADMINS` | executive | Organisation administration |
| `PROGRAMME_MANAGERS` | evidence manager, executive | Programme and project lifecycle decisions |
| `PROJECT_EDITORS` | evidence manager, executive, researcher, field officer | Day-to-day recording against a project |

### SUPER_ADMIN is an organisation role

`Role.SUPER_ADMIN` carries full rights **inside its own organisation only**. It
does not grant access to any other tenant.

Platform-level administration is a separate flag, `User.is_superuser`.

This distinction was introduced because the obvious implementation —
"holds SUPER_ADMIN somewhere, therefore is a platform admin" — means the
administrator of one small tenant can read every other tenant's data. That
version was written, caught by a tenancy test, and replaced.

## 3. Multi-tenant isolation

Every tenant-owned record carries `organisation_id` explicitly, including
stories, which could otherwise only be scoped by joining through evidence.

A record outside the caller's organisations is reported as **404, not 403**.
Returning 403 would confirm that the id exists in another tenant, which is
itself a disclosure. The same rule applies to the public portal: an
unpublished record is reported as missing, so the portal cannot be used to
probe for drafts.

A filter that names an organisation can only ever narrow what a caller sees.
Passing another tenant's `organisation_id` to search returns nothing rather
than widening access.

## 4. Separation of duties

`require_distinct_actor` enforces that two consecutive steps in a workflow are
carried out by two different people. **A platform admin is not exempt**: the
point of the check is that two people looked at the record, so bypassing it
for anyone would defeat it.

Enforced separations:

| Workflow | Separation |
|---|---|
| Evidence | The verifier may not approve. |
| Story | The author may not approve. The approver may not publish. |
| Question | The person who drafted the answer may not approve it. The approver may not publish it. |

## 5. Mass assignment

Request bodies are typed Pydantic schemas, never raw dicts. Workflow state —
status, verification state, approval state, `verified_by`, `approved_by`,
`is_published`, `organisation_id`, `created_at`, `id` — is **absent** from
every update schema. Those transitions belong to dedicated endpoints that
enforce the rules.

This was a real defect: `BaseRepository.update()` performs an unconditional
`setattr` for every supplied key, so an untyped body meant a single PUT could
set its own approval state or move a record between tenants.

## 6. Stale approvals

An approval covers the content that was in front of the approver. Editing a
record that has been verified or approved therefore:

1. raises its `version`, and
2. returns it to draft, clearing the sign-off.

Without this, a record could be approved, quietly changed, and then published
on an approval that never covered what went out. Each approval record stores
the `entity_version` it was made against, so the trail shows exactly what was
reviewed.

Editing a published record is refused outright. It must be withdrawn first,
which archives it with a stated reason rather than erasing the fact that it
was public.

## 7. Input handling

- SQL is built through SQLAlchemy expressions. Search terms reach Postgres as
  bind parameters; the prefix form of a `tsquery` is constructed only from
  input already matched against `^[\w\s]+$`, which keeps it out of tsquery's
  own operator syntax as well.
- The public question endpoint is rate-limited as a spam channel.
- A drafted answer is carried in the request body, not the query string. An
  answer in a URL is written into every access log and proxy along the way.

## 8. Secrets

No secret is committed. The application refuses to start in production with a
default or missing secret key. `.env` files are ignored by git; `.env.example`
carries placeholder values only.

## 9. Audit trail

Every state transition writes an `audit_log` entry: who, what, when, from
which address, old values and new values. Action names are stable identifiers
rather than prose, because they are queried and reported on.

The audit write is committed separately from the change it describes and
raises on failure rather than passing silently — an unrecorded state change is
the thing the module exists to prevent.

## 10. What is not enforced

Stated plainly, because a security document that only lists strengths is
misleading:

- **Rate limiting is per-process by default.** Point `RATE_LIMIT_STORAGE_URI`
  at Redis before running more than one worker.
- **The approval trail is append-only by convention.** Nothing in the schema
  stops a direct database write from altering it.
- **No field-level encryption.** Submitter addresses are stored in plain text.
- **No account lockout** after repeated failed logins, only rate limiting.
- **No MFA.**
- **No signed audit entries**, so the trail is evidence of what the
  application did, not proof against a database administrator.
