# Intelligence and dashboards

Spec sections 21–22. "Intelligence" is the word in this specification that most
needs pinning down, because it is where profiling would arrive if it were going
to.

Section 4 forbids voter profiling, political preference inference,
psychological profiling and susceptibility scoring, and requires that all
intelligence be **explainable, source-linked and auditable**. So intelligence
here means exactly one thing:

> Counting the platform's own records, and being able to show which ones.

It is analysis of what a body has evidenced, been asked and done. It is never
analysis of people.

---

## 1. Every figure carries its own basis

A number on a dashboard that cannot be checked is an assertion, and this
platform does not make those anywhere else.

Every figure returns a `basis` — the measure and the filters that produced it —
and `GET /intelligence/records` takes exactly that basis back and returns the
rows:

```json
{
  "label": "Published evidence",
  "value": 4,
  "suppressed": false,
  "basis": {"measure": "evidence", "dimension": "status", "value": "published"}
}
```

```
GET /intelligence/records?measure=evidence&dimension=status&value=published
→ {"total": 4, "basis": {...}, "data": [ ...the four records... ]}
```

This is tested rather than asserted. `test_every_overview_figure_reconciles_
with_its_drill_down` walks every figure the overview serves, hands its basis
straight back, and requires the totals to agree. Disabling the basis filter
makes that test fail, which was checked rather than assumed.

## 2. A bucket too small to be anything but a person is suppressed

Breaking citizen-submitted questions down by category and area is genuinely
useful. It is also one step from identifying who asked what.

Where a measure records things **individuals submitted**, a bucket below
`MIN_CELL_SIZE` (5) is withheld rather than counted.

| | |
|---|---|
| **Suppressed** | `questions` — submitted by members of the public |
| **Not suppressed** | `evidence`, `projects`, `missions`, `integrity_signals`, `scenarios` |

Evidence and projects record public works, not people. Hiding "three boreholes
in this ward" would conceal the state of public information in the name of a
privacy that is not at stake.

**A zero is reported as a zero.** "Nobody asked about this" is not sensitive,
and withholding it would make the breakdown unreadable. It is the small
non-zero bucket that identifies.

### Complementary suppression

Suppressing one bucket is not enough on its own. Given:

```
water 8 · roads 5 · sanitation 2      total 15
```

withholding only sanitation leaves `15 − 8 − 5 = 2` — exactly the number the
threshold existed to hide. So when anything is suppressed, the smallest
reported bucket goes with it:

```
water 8 · roads SUPPRESSED · sanitation SUPPRESSED      residual 7 over two buckets
```

The cost is real and worth stating: a bucket large enough to publish is
withheld. That is the price of the first one being genuinely hidden. **A
threshold that can be subtracted away is worse than none**, because it implies
a protection that is not there.

## 3. What cannot be asked

Dimensions are a **closed set** per measure. A caller cannot group by an
arbitrary column, so no dimension can become a route to a field nobody meant to
aggregate:

```
GET /intelligence/breakdown?measure=questions&dimension=submitter_email
→ 400  "'questions' cannot be broken down by 'submitter_email'.
        Available: category, geography_id, language, status"
```

A test asserts directly that no measure offers a dimension that groups people
rather than records — `submitter_email`, `created_by`, `assigned_to`,
`reported_by`, `is_anonymous` and the rest. It fails if one is ever added.

The 400 names what *would* have worked. A refusal that does not is a dead end.

## 4. Why the drill-down is not suppressed

`/intelligence/records` returns the rows without applying the threshold, and
that is correct rather than an oversight.

Suppression stops an **aggregate** from describing an individual to someone who
could not otherwise see them. A caller who may read the underlying records
already may — they are that organisation's own records, scoped as everything
else is. The threshold protects the shape of a published summary; it is not a
second access control over records their custodians can already open.

A drill-down is scoped exactly as the figure was, so it can never reach further
than the number it explains.

## 5. What is not built

- **No front end.** The API is complete and exercised; there is no dashboard
  screen.
- **No time series.** Every figure is a count as of now. Trend over time would
  need either a period filter on each measure or stored snapshots, and neither
  is here.
- **No saved or published intelligence reports.** §21 implies an analyst
  writing something up. That would be content, and content on this platform
  goes through an approval workflow — so it belongs with stories rather than
  bolted onto a read-only analytics layer.
- **No cross-organisation comparison.** Every figure is scoped to the caller's
  own tenants. Comparing bodies against each other is a different and much more
  sensitive product than counting your own records.
- **Nothing is cached.** Every figure is computed on request, which is why it
  can always be reconciled. At a scale where that hurts, the answer is a cache
  with the basis as its key — not a stored number nobody can check.
