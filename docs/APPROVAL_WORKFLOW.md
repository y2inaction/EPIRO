# Approval workflows

Spec section 36 requires that an approval be **recorded**, storing reviewer,
timestamp, decision, comments and version, and that workflows be
**configurable**.

The recording is CONFIRMED. The configurability is **NOT BUILT** — the stages
below are fixed in code. An organisation cannot define its own. See
`docs/STATUS.md`.

---

## 1. The approval trail

One table, `approval_record`, serves every content type. It is addressed by
`(entity_type, entity_id)` rather than by a foreign key per kind, so evidence,
stories and questions share one trail instead of each growing its own set of
approval columns.

| Column | Purpose |
|---|---|
| `entity_type`, `entity_id` | What was decided on. |
| `entity_version` | The version the decision covered. |
| `decision` | `approved`, `rejected` or `changes_requested`. |
| `reviewer_id` | Who decided. |
| `decided_at` | When. |
| `comments` | Why. Required on a rejection. |

**Every round is kept, including the ones that refused.** The previous design
stored only the latest approver id on the record itself, so a rejection left no
trace at all and `EvidenceStatus.REJECTED` was a state nothing could reach.
The history of what was turned down is as much a part of accountability as
what went through.

`entity_version` is what makes the trail meaningful. A record's version is
raised on every content edit, and an edit to something already approved
returns it to draft — so an approval can never end up describing content its
approver never saw.

## 2. Evidence

```
draft ──verify──▶ verified ──approve──▶ approved ──publish──▶ published
                     │           │                                │
                  reject      reject                          withdraw
                     ▼           ▼                                ▼
                 rejected    rejected                         archived
```

| Step | Role | Rules |
|---|---|---|
| Verify | `EVIDENCE_VERIFIERS` | — |
| Approve | `APPROVERS` | Must already be verified. **The verifier may not approve.** |
| Reject | `APPROVERS` | Reason required. Published evidence cannot be rejected — withdraw it. |
| Publish | `PUBLISHERS` | Must be approved. |
| Withdraw | `PUBLISHERS` | Reason required. Archives rather than deletes. |

Approving evidence that carries a measurement also moves its indicator's
current value — so a figure on a dashboard always traces back to an approved
record. An older measurement approved late does not overwrite a newer one.

## 3. Stories

```
draft ──submit──▶ in_review ──approve──▶ approved ──publish──▶ published
  ▲                   │                      │                      │
  │                reject                 reject                withdraw
  │ (edit)             ▼                      ▼                      ▼
  └───────────────  rejected ──submit──▶  rejected              archived
```

| Step | Role | Rules |
|---|---|---|
| Submit | `CONTENT_AUTHORS` | From draft or rejected. |
| Approve | `STORY_APPROVERS` | **The author may not approve.** The supporting evidence must itself be approved. |
| Reject | `STORY_APPROVERS` | Reason required. Clears any existing approval. |
| Publish | `PUBLISHERS` | **The approver may not publish, and neither may the author.** Evidence is re-checked, because it can be withdrawn between approval and publication. |
| Withdraw | `PUBLISHERS` | Reason required. Also drops the story from the featured set. |

Publication used to be a single call that set the approver, the approval date
and the publication date together — whoever pressed publish *was* the
approval, so nothing ever separated signing off public information from
releasing it.

## 4. Questions

```
new ──triage──▶ triaged ──respond──▶ response_drafted ──approve──▶ approved ──publish──▶ published
                   ▲                        │                          │
                   │                     reject                     reject
                   └── researching ◀────────┴──────────────────────────┘
```

| Step | Role | Rules |
|---|---|---|
| Triage | `QUESTION_RESPONDERS` **in the receiving organisation** | Assigns the question to a body. |
| Respond | `QUESTION_RESPONDERS` | Answer carried in the request body. |
| Approve | `APPROVERS` | **The person who drafted the answer may not approve it.** |
| Reject | `APPROVERS` | Reason required. Returns to research and clears any approval. |
| Publish | `PUBLISHERS` | **The approver may not publish.** |
| Close | `QUESTION_RESPONDERS` | No further responses. |

Triage is the only step whose role is checked against an organisation the
record does not yet belong to. It has to be: a publicly submitted question
belongs to nobody until someone claims it, so there is no tenant to check
against. Without this step every public question was permanently stuck.

## 5. The one fact base rule

Nothing goes public that is not traceable to approved evidence.

- A story cannot be approved unless its evidence is approved or published.
- A story cannot be published if its evidence was withdrawn in the meantime.
- A published story carries the permanent reference of its evidence, so a
  reader can follow the claim back to the record it rests on.

## 6. What configurability would require

Recorded here so the gap is actionable rather than vague. A configurable
engine (§36) needs:

1. A workflow definition per organisation and content type: an ordered list of
   stages, each naming the role that may act and whether it requires an actor
   distinct from the previous stage.
2. A current-stage pointer on each record, replacing the fixed status enums.
3. Migration of the three hard-coded lifecycles above into default definitions,
   so existing behaviour is preserved.
4. Validation that a definition cannot remove a separation of duties that the
   platform guarantees — an organisation must not be able to configure away
   the rule that the author cannot approve their own work.

Point 4 is the one that matters: configurability must not become a way to
switch off accountability.
