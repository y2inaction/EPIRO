# Field operations and missions

Spec section 18. A mission is planned, authorised, carried out, checked in on,
and written up. Evidence gathered on it is filed against it and goes through
the same verification as anything else.

This is the part of EPIRO whose cost falls on people rather than on records, so
most of this document is about what it refuses to do.

---

## 1. No approval without a written risk assessment

Sending people somewhere is the most consequential thing the platform
authorises. `POST /missions/{id}/approve` refuses while `risk_assessment` is
empty or blank, and there is no path through the API that gets round it.

A whitespace-only assessment does not count. That is not pedantry: a field that
can be satisfied with a space is a field that will be.

## 2. The planner may not approve their own mission

The same separation the platform applies to publishing information, applied to
sending people out. Somebody other than the person who wants to go has to have
read the risk assessment and agreed the trip is worth it.

## 3. What is deliberately not collected

A field mission database records where named members of staff will be and when.
That is a duty-of-care necessity and also, built carelessly, a movement log for
the people who do the most exposed work on the platform.

Spec section 20 limits collection to what legitimate operational purposes
require. It is written about citizens. Staff did not stop being people by being
employed, so the same reasoning applies.

| Wanted | Recorded | Not recorded |
|---|---|---|
| Where to send help | The mission's area and window | A position per person |
| Whether the team is all right | A check-in **state**: safe, delayed, assistance required | A stream of coordinates |
| Who is out there | The team on the mission | Where each of them went |
| What the mission found | Evidence records through the source registry | A list of the citizens spoken to |

**`mission_check_in` has no latitude, longitude or geometry column**, and
neither does `mission_member`. Tests assert this directly, because the way this
gets lost is not a decision to build tracking — it is somebody adding "just a
lat/long, for safety" three phases from now.

A check-in carries a free-text note. A team that wants to say where it is can;
the platform does not require it and does not parse it into a track.

## 4. Overdue is derived, never stored

Whether a team has missed a check-in is computed from the last check-in and the
mission's interval, the same way a scenario's readiness floor is computed.

A stored flag would need something to set it — a scheduled job, a trigger —
and that something is exactly what fails at the same time as everything else
when a mission goes wrong. Derived on read is slower and correct.

The cost is honest: `GET /missions/?needs_attention=true` filters in Python
after loading rather than in SQL, because the predicate is not a column. That
trade is stated in the endpoint's own docstring.

A mission that has started and never reported is measured from its start, so a
team that leaves and is never heard from is overdue rather than silently fine.
A mission that has not started is never overdue — a team that has not left is
not missing.

## 5. The lifecycle

```
planned ──approve──▶ approved ──start──▶ in_progress ──complete──▶ completed
   │                    │                     │
 cancel               cancel              cancel (a recall)
   ▼                    ▼                     ▼
             cancelled, with a stated reason
```

| Step | Role | Rules |
|---|---|---|
| Plan | `FIELD_COORDINATORS` | Executive, evidence manager. |
| Edit | `FIELD_COORDINATORS` | **Only while still planned.** What was approved is what somebody signed off on. |
| Approve | `FIELD_COORDINATORS` | Risk assessment required. **Not the planner.** |
| Start | `FIELD_TEAM` | Must be approved. From here the mission is watched. |
| Check in | `FIELD_TEAM` | State and an optional note. |
| Complete | `FIELD_TEAM` | Report required. |
| Cancel | `FIELD_COORDINATORS` | Reason required. A mission under way can be called off — that is a recall. |

A completed mission cannot be cancelled. What happened, happened.

## 6. Field capture is idempotent

A device on a bad connection retries. A capture endpoint that filed the same
observation twice could not be built on later, so:

```
POST /missions/{id}/evidence
{"capture_key": "<client-generated, unique per organisation>", ...}

201 Created  — first time
200 OK       — this key was already used; here is the record it made
```

A retry returns the **original** record, unchanged. It is not a revision: the
same request arriving twice should not overwrite what the first one filed.

Two things make this hold rather than merely usually hold:

- A **partial unique index** on `(organisation_id, capture_key)` where the key
  is not null. The database refuses the duplicate; the application does not
  race to check for one first.
- An **IntegrityError branch**. Two retries arriving at once both look, both
  find nothing, and both insert. The index settles it, and the loser's correct
  answer is the record the winner created — not a 500. Without this, the
  promise that a retry is safe would hold only when the retries were far
  enough apart, which is exactly not the case on the connection that caused
  the retry.

A field capture starts as an **unverified draft**, like any other evidence.
Going and looking is how a record is gathered; it is not a reason to skip
verification.

## 7. What is not built

- **Offline capture and sync (§17).** Not built, and not claimed. The
  idempotent capture key is the part of it that could not be retrofitted — it
  is groundwork, not the feature.
- **No front end.** The workflow is complete in the API and exercised end to
  end; there is no mission screen.
- **No alerting.** An overdue mission appears on `?needs_attention=true` when
  somebody looks. Nothing pages anyone; notifications are §45 and not built.
  **This matters more here than elsewhere in the platform**, because the thing
  nobody is looking at is a team that has not reported in.
- **No geofencing or route planning.** Both would need the per-person location
  this deliberately does not collect.
