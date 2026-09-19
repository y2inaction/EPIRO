# The decision register

Phase 4: connecting intelligence to decisions.

The specification draws a chain, and everything up to the last link was
already built:

```
Evidence → Signal → Assessment → Finding → Readiness implication → Action / owner → Status
```

An organisation that can evidence, assess and conclude but cannot say what it
decided to do about any of it has built a filing system. The action register
is the last link, and it is the one that decides whether the rest is
accountability or record-keeping.

---

## 1. An action must cite what prompted it

`origin_type` and `origin_id` are both required, and the cited record is
checked to exist **inside the caller's organisations** before the action is
accepted. Four origins are offered: an integrity signal, a drill finding, a
scenario, or an evidence record.

```
POST /actions/  {"origin_type": "integrity_signal", "origin_id": "…", …}
→ 400  "No integrity signal with that id in your organisations. An action has
        to cite something that exists, or the citation means nothing."
```

Checked rather than trusted, for two reasons. An origin pointing at nothing
makes the citation decorative — a register of actions nobody can trace back to
a finding is a wish list. And an origin pointing into another organisation
would let a caller discover which identifiers are real there by watching which
ones are accepted.

The chain reads in both directions: `GET /actions/origin/{type}/{id}` answers
"what did we decide because of this finding", and a finding with nothing
against it is something the organisation knows and has not acted on.

## 2. An action must have an owner

`owner_id` is not nullable. Unowned work is not work, and an action filed for
"the team" is one nobody has agreed to do.

## 3. Closing requires a written outcome

`done` and `dropped` both require `outcome`, and whitespace does not count —
the rule lives in the service rather than only in the schema, because
`"   "` passes a length check and is still not an account of anything.

The status is not the interesting part; what happened is. A record that moved
to "done" with no account of what was done explains nothing to whoever reads
it six months later.

**Deciding not to act is an outcome, not a deletion.** `dropped` keeps the
decision and its reasoning. Deleting the row would keep neither, and the
reason for not acting is usually the part worth having when somebody asks why
nothing happened.

## 4. The lifecycle, and why it does not reverse

```
proposed → accepted → in_progress → done
    └───────────┴────────────┴──────→ dropped
```

A closed action is not reopened. A decision that was carried out and then had
to be revisited is a **new** decision, with its own reasoning and its own
trail; editing the old one over the top would lose the fact that it happened
twice.

## 5. Overdue is derived, never stored

A stored flag is wrong from the moment the clock passes it until something
updates it, and the thing least likely to happen to a neglected action is an
update. `overdue` is computed on every read from the due date and the status,
and a finished action is not chased past its date. A test asserts there is no
`overdue` column to fall out of step.

## 6. What is deliberately absent

**No computed priority.** Ranking what matters is a judgement an accountable
person makes. A generated score would launder that judgement into arithmetic
nobody can argue with, and a test asserts no `priority_score`, `urgency` or
`risk_score` column has appeared.

**No filter or dimension by owner.** Who owns an action is on the action,
where it is accountability. A register that can be sliced by person is a
report on staff, and spec section 4's prohibition on profiling is not only
about citizens — the same line is held for drill findings, mission check-ins
and the change feed.

## 7. It is part of the intelligence layer

Registering `actions` as a measure means the register is counted, filtered,
broken down and read in the change feed by the same mechanism as everything
else — no separate reporting path to drift out of step:

- **Overview** carries an `Actions` figure that reconciles with its records.
- **Unresolved** carries three: proposed and not accepted, accepted and not
  started, under way.
- **Changes** reads the decision trail: what was decided, when, and by whom.
- The **filters** apply: organisation, area, theme, status, date range.

## 8. What is not built

- **No front end.** The API is complete and exercised; there is no screen for
  raising or running an action.
- **No notification when an action falls overdue.** The register can say what
  is late; nothing tells anybody.
- **No dependency between actions**, and no grouping into a plan.
- **No separation of duties on closing.** The owner records their own outcome.
  Whether completing an action should need a second person is a real question
  and was not decided here; the evidence and story workflows do require it,
  and this deliberately does not claim to.
