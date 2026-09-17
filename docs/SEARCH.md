# Search

Spec section 35: one search across the platform's content, filtered by date,
geography, theme, source, status, organisation, verification and owner.

---

## 1. Why this was rebuilt

Search was `ILIKE '%term%'` across four tables. A leading wildcard makes a
B-tree index unusable, so **every search was a sequential scan of the whole
table**. No index existed that could have helped, and no amount of tuning
would have changed that — the query shape itself was the problem.

It also could not match across word forms: a search for "flood" would not find
"flooding".

## 2. How matching works now

Each searchable table carries a `search_vector` column: a `tsvector`,
**generated** by the database and stored, with a GIN index over it.

Generated rather than trigger-maintained on purpose. A trigger the application
forgets to fire, or a write path that skips the update, leaves a row that has
quietly stopped being findable. A generated column cannot get out of step with
the row it describes.

Columns are weighted, and `ts_rank_cd` orders the results, so a title hit
outranks a passing mention deep in a body:

| Table | `A` | `B` | `C` |
|---|---|---|---|
| evidence | reference, title | description | outcome |
| project | name, code | description | — |
| story | title, headline | summary | body |
| question | question_text | response | category |
| scenario | name | description | trigger |

Evidence includes its permanent reference in the vector, so a record is
findable by the identifier it is cited by.

## 3. Query parsing

| Input | Treated as |
|---|---|
| `borehole` | Prefix match — `borehole:*`. Type-ahead: "boreh" finds "Borehole". |
| `clinic rehabilitation` | All terms must match, each as a prefix. |
| `"borehole rehabilitation"` | Quoted phrase, matched in order. |
| `borehole -clinic` | Exclusion. |
| `borehole OR clinic` | Either. |

Plain word input goes through `to_tsquery` with prefix operators; anything
containing quotes, minus signs or `OR` goes through `websearch_to_tsquery`.

Terms are always bound as parameters, never interpolated into SQL. The prefix
form is built only from input already matched against `^[\w\s]+$`, which keeps
user text out of tsquery's own operator syntax too.

## 4. Filters

All eight filters section 35 names are implemented. A filter applies where the
content type can express it:

| Filter | evidence | project | story | question | scenario |
|---|:-:|:-:|:-:|:-:|:-:|
| date | ✓ | ✓ | ✓ | ✓ | ✓ |
| geography | ✓ | ✓ | — | ✓ | — |
| theme | ✓ | — | — | — | — |
| source | ✓ | — | — | — | — |
| status | ✓ | ✓ | ✓ | ✓ | ✓ |
| organisation | ✓ | ✓ | ✓ | ✓ | ✓ |
| verification | ✓ | — | — | — | — |
| owner | ✓ | ✓ | ✓ | ✓ | ✓ |

**A type that cannot express a filter that was set is left out of the results
entirely**, rather than returned unfiltered. Returning it would present those
records as matching a filter that was never applied to them, which is a false
claim about the data.

The geography filter matches the named area **and every area beneath it**, via
a recursive CTE. "Everything in this state" reaches records pinned to its
wards, which is what a user means by it.

An organisation filter can only narrow. Naming a tenant the caller does not
belong to returns nothing.

## 5. Content types not covered

Section 35 also names documents, stakeholders, field missions, intelligence,
media and tasks. Those entities do not exist yet, so search cannot cover them.

The API returns them in an `unsearchable_types` field rather than silently
omitting them — the difference between a known gap and a result that looks
complete but is not.

## 6. Public search

`/api/v1/public/search` runs against the same indexes over a set restricted to
published records, so nothing under review can be discovered by guessing at
search terms.

## 7. Substring lookups

Some lookups are legitimately substring matches rather than word search: area
names, thematic area names, and the user directory. Those are backed by
`pg_trgm` GIN indexes, which *can* serve `ILIKE '%term%'`.

`pg_trgm` and `postgis` are created by the baseline migration and by
`infrastructure/postgres/init.sql`, so a database provisioned by migration
alone works.

## 8. Known limitation

The text search configuration is `english` for all content, including content
in Hausa, Nupe or Pidgin. Stemming will be wrong for those languages: an
English stemmer applied to Hausa produces tokens that match nothing useful.

Fixing it properly means a per-language configuration and a vector per
language, with the query side choosing the configuration from the content's
language code. The configuration name is a single constant, `SEARCH_CONFIG`,
deliberately shared by the model and the query layer so the two cannot drift —
a tsquery parsed with a different configuration silently stops matching.
