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

## 3. Filters, and why one is refused rather than ignored

Every figure can be narrowed by six things: organisation, area, theme,
verification state, status, and a date range.

**A filter is part of the basis.** It is carried inside each figure's own
`basis` and travels into the drill-down, because a figure narrowed by
something its basis did not carry would count one set of records and link to
another — a failure that looks exactly like success. A test applies a theme
filter to the whole overview and requires every figure to both carry it and
reconcile.

**A measure that cannot honour a filter refuses it.** Only evidence records a
verification state; only three measures carry a theme. Quietly dropping the
filter would serve an unfiltered count under a filtered heading, which is
wrong in the one way nobody checks. So `/intelligence/measures` says which
filters each measure takes, a client sends only those, and anything else is a
400 naming what would have worked.

On a list that spans measures — the overview, the unresolved list — refusing
outright would make the filter useless and counting the rest unfiltered would
be a lie, so the measures that cannot honour it are left out and **named** in
`excluded_measures`. A figure missing from a list and a figure that counted
nothing look identical and mean opposite things.

**The dates are recording dates.** `since` and `until` narrow on when the
platform recorded something, not when the thing happened. For evidence those
differ: a borehole handed over in June and recorded in September is a
September record. Using each measure's own event date would make the measures
incomparable — a count of "things that happened" added to a count of "things
we learned" — so one meaning is used throughout, and the filter bar says so
where the control is rather than in a footnote.

## 4. What is still open

`/intelligence/unresolved` answers the question a dashboard is usually worst
at. Finished work is easy to count; work that is waiting is not, and a
platform that only reports volume will always look busier than it is
accountable.

Every figure is **one open state of one measure** — evidence nobody has
checked, questions claimed but unanswered, claims looked at and unsettled,
missions still in the field, scenarios at red. Single-valued deliberately: a
basis expresses one equality, so each figure drills down to exactly the
records waiting. A broader definition ("anything not published") would read
better in a heading and could not be checked against its own rows, and a
figure nobody can check is the thing this layer refuses to serve.

## 5. What cannot be asked

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

**The filters are a closed set for the same reason**, and none of them names a
person: not the author, not the reviewer, not the assignee. Who verified a
record is on that record's own approval trail, where it is accountability. The
same fact as a filter across aggregates is a league table of staff, and
section 4's prohibition on profiling is not only about citizens — the same
line is held for drill findings, which record what the response could not do
rather than who let it down, and for mission check-ins, which record a state
rather than a position. A test asserts no filter ending in `_by` and no filter
from a list of person-shaped names has appeared.

## 6. Why the drill-down is not suppressed

`/intelligence/records` returns the rows without applying the threshold, and
that is correct rather than an oversight.

Suppression stops an **aggregate** from describing an individual to someone who
could not otherwise see them. A caller who may read the underlying records
already may — they are that organisation's own records, scoped as everything
else is. The threshold protects the shape of a published summary; it is not a
second access control over records their custodians can already open.

A drill-down is scoped exactly as the figure was, so it can never reach further
than the number it explains.

## 7. The dashboard

The hub is `/workspace/intelligence`, with a section per measure:

```
/workspace/intelligence            Overview — the headline figures
        ├── /unresolved            What is still waiting
        ├── /evidence              Evidence records, every dimension
        ├── /questions             Questions from the public
        ├── /integrity             Information integrity signals
        ├── /missions              Field missions
        ├── /scenarios             Readiness scenarios
        ├── /projects              Projects
        └── /records               The records behind any figure
```

A section asks the server what that measure can be broken down by and renders
one panel per dimension, so a dimension added on the server appears without
the front end changing, and one removed stops being offered rather than
becoming a panel that refuses.

**The filter bar is a plain GET form**, so the filters end up in the URL. A
filtered view is then something a person can bookmark and send to a colleague,
and it works with scripting off. Three consequences worth stating:

- **A section offers only the filters its measure takes**, from the catalogue.
  Anything else set is dropped before the request and **named on the page**,
  because the server refuses what it cannot apply and a silent drop would be
  worse than either.
- **Organisation, area and dates travel with you through the nav.** Status and
  verification state do not: "published" means one thing for evidence and
  another for a question, so carrying one across would quietly change what it
  selected.
- **The status options come from an unfiltered breakdown.** Drawing them from
  the filtered one would leave the select holding only the value already
  chosen, so a reader could narrow once and never change their mind.

**A section has no total at the top, deliberately.** A total is a summary
figure, and the overview already serves those with suppression applied. The
only other place to get one is the drill-down, which is unsuppressed by design
(see §6) — so putting that number at the head of a summary page would place an
unsuppressed aggregate exactly where the threshold exists to prevent one.

Two decisions in the rendering are worth stating because they are where the
rules above either survive contact with a screen or quietly stop holding.

**Every number is a link.** A headline figure is a stat tile that links to
`/workspace/intelligence/records` carrying its own basis; every bucket in a
breakdown links the same way. The reconciliation the API is tested for was
checked again through the interface: every figure on the overview and every
bucket in all six sections was read off the rendered page, its link followed,
and the drill-down's total compared. All of them agreed.

That check matters most on a dimension that groups by identifier. `geography_id`
and `thematic_area_id` come back keyed on a UUID, which is no answer to
anything, so those buckets are given names from `/geography` and
`/thematic-areas`. The row then shows a name while its link must still carry
the identifier — show the name and link by the name and every one of those
rows silently counts nothing. A bucket whose name cannot be found keeps its
identifier and the panel says the lookup failed, rather than the row being
dropped: the count is real either way.

**A withheld bucket is a table row, not a missing bar.** This is why the
breakdowns are tables rather than bar charts. A suppressed bucket cannot be
drawn as a bar: zero length says it is zero, and leaving it out says it does
not exist, and both are false about a bucket whose only problem is being
small. In a table the bar is one column, and a row with no bar to draw uses
that space to say `Fewer than 5 records`, with the reasoning once beneath the
table.

Two smaller consequences of the same rule:

- **Bars scale to the largest *reported* bucket.** Scaling to a withheld one
  would let its value be measured off the others with a ruler — the
  suppression defeated by geometry rather than by arithmetic.
- **A withheld figure still links to its records**, and the drill-down says
  why that is not a contradiction: the threshold protects the shape of a
  published summary, not an organisation's records from its own staff.

## 8. What is not built

- **No time series.** Every figure is a count as of now. Trend over time would
  need either a period filter on each measure or stored snapshots, and neither
  is here.
- **No saved or published intelligence reports.** §21 implies an analyst
  writing something up. That would be content, and content on this platform
  goes through an approval workflow — so it belongs with stories rather than
  bolted onto a read-only analytics layer.
- **No cross-organisation comparison.** Every figure is scoped to the caller's
  own tenants, and the organisation filter only ever narrows within them.
  Comparing bodies against each other is a different and much more sensitive
  product than counting your own records.
- **No change over time, only a window.** A date range answers "how many in
  September". It does not answer "what changed": that needs either two windows
  compared or the audit trail read as a feed, and neither is built. The trail
  itself exists — every state transition writes an entry with its actor and
  timestamp — so the question is answerable per record on its own approval
  trail, just not in aggregate here.
- **The name lookup is capped at one page.** Breakdowns by area and theme
  resolve their buckets against the first 1000 areas and themes, which is the
  API's own maximum page. Past that a bucket shows its identifier and the
  panel says so. The proper fix is an endpoint that resolves a set of
  identifiers to names, rather than fetching everything to build a map.
- **Nothing is cached.** Every figure is computed on request, which is why it
  can always be reconciled. At a scale where that hurts, the answer is a cache
  with the basis as its key — not a stored number nobody can check.
