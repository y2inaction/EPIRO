# Privacy and data governance

Spec section 20: *"Do not create a hidden citizen surveillance system. Only
collect data necessary for legitimate operational purposes."*

This document records what the system collects about members of the public,
what it refuses to collect, and where those refusals are enforced in code.

---

## 1. What is collected about a citizen

The only route by which a member of the public puts data into EPIRO is
submitting a question. That record holds:

| Field | Why it exists |
|---|---|
| `question_text` | The question itself. |
| `language` | To answer in the language it was asked in. |
| `location_state`, `location_lga` | Free text as the submitter typed it, so the answer can be about the right place. |
| `geography_id` | The resolved area, set during triage. Kept alongside the free text rather than replacing it, so what was actually said is preserved. |
| `category` | For routing to the right team. |
| `is_anonymous` | Whether the submitter wants to be contacted. |
| `submitter_email` | Only when `is_anonymous` is false. |

Nothing else. There is no profile, no submission history tied to a person, no
device fingerprint, no tracking identifier.

## 2. Enforced refusals

These are not policy statements. They are checks in the code with tests
against them.

### An anonymous submission cannot carry an address

`QuestionCreate` rejects a payload with `is_anonymous: true` and a
`submitter_email`. A record that describes itself as anonymous while holding a
contact detail is a false statement to the person who sent it.

### A submitter is never published

`is_anonymous` governs whether the body may **contact** the submitter. It does
not govern whether they may be **named publicly** — they may not, either way.
The public portal's question schema has no field for it.

### The audit trail does not record who asked

The audit entry for a public submission deliberately carries neither the
submitter's address nor the text of the question. The trail exists to hold the
organisation to account for how it handled a question, not to accumulate a
record of the people who ask them.

This is the one place where the audit trail is deliberately less complete than
elsewhere, and the reason is in the code comment.

### The public portal identifies no individual at all

Not the author of a story, not the verifier of an evidence record, not the
approver, not the publisher. The reader is entitled to know **how far
verification got** — the state is published — but not who signed it off.

Public responses are built from allow-list schemas in `app/schemas/public.py`
rather than the internal ones. Reusing an internal schema would mean every
field the domain later grows is published to the world by default. A test
walks every public response at any depth and fails on a forbidden field.

## 3. What the system does not do

Spec section 4 forbids the following, and none of it exists anywhere in the
codebase. Listed so a later contributor understands the absence is a decision:

- Voter profiling or political preference inference.
- Political susceptibility scoring.
- Demographic political targeting or microtargeted political messaging.
- Covert influence operations.
- Automated political persuasion.
- Psychological profiling for political purposes.
- Deceptive identity systems.

There is no model, column, endpoint or job for any of these. If a future
change appears to require one, that is a signal the change is out of scope,
not a signal to add the field.

## 4. Retention

**NOT BUILT.** There is currently no retention policy, no expiry job and no
deletion schedule for submitter addresses. A question record keeps its address
indefinitely once given.

This is a genuine gap, and it is stated here rather than left to be
discovered. Implementing it means: a retention period per data class, a job
that clears `submitter_email` once the question is closed and the retention
window has passed, and an audit entry recording that the clearance happened.

## 5. Subject access and erasure

**NOT BUILT.** There is no endpoint by which a person can ask what is held
about them or ask for it to be deleted. Because the only personal datum is an
email address on a question, the implementation is small — but it does not
exist today.

## 6. Data location

All data is in one PostgreSQL database. There is no third-party analytics, no
external logging service and no outbound data sharing configured. The only
outbound network dependency in the running application is the database and
Redis.
