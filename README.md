# quarry

A lexical full-text search engine built from the postings up, with the
operational machinery a real deployment grows around it: 186 modules, 13
self-grading relevance evals, 10 runnable examples, and 1,900+ tests, all
in pure Python with no dependencies beyond the standard library.

## What lives here

**The engine core.** An analyzer with declared trade-offs (lowercase,
stopwords, a light stemmer that documents what it mangles), immutable
segments with tombstone deletes and tiered merging, positional postings,
BM25 with cross-segment global statistics, a query language with fields,
phrases, required and prohibited terms and OR groups, offset-free
pagination by (score, id) token, highlighting, fuzzy suggestions behind a
did-you-mean that never second-guesses a word the corpus contains, spans,
facets, ranges, synonyms with expansion discounts, and cross-field dismax
scoring where the best field wins and the rest whisper.

**The quality suite.** Thirteen evals in `quarry/evals/`, each one an
experiment whose conclusion is chained to its numbers: idf wins, phrase
precision, the stemming trade, length normalization, deterministic ties,
synonym gain, proximity gain, collapse fairness, accent folding, deadline
honesty, cost-model truth, fuzzy quality, and pagination truth. Broken
expectations are reported, not hidden, and several evals deliberately pin
measured limits (the merge-intersect cost divergence, the pagination
statistics-drift overlap) so the day the engine improves, the eval breaks
on purpose and demands its own update.

**The operations wing.** Journal with checksummed replay, manifests with
digest verification, backpressure with hysteresis, load shedding priced by
the cost model, quotas, retention with legal holds, chaos drills, canary
rollouts, shadow indexing with a numeric cutover bar, feature flags, freeze
windows with loud overrides, hedged reads, read repair and anti-entropy,
hybrid logical clocks, fencing write locks, rebuild planning, runbooks as
data, alert deduplication, SLO burn accounting, drift watching, capacity
planning, and a launch board where four gates report in their own words.

**The craft drawer.** Varint-coded postings, front-coded dictionaries,
skip pointers justified by their own probe counters, Bloom filters and
MinHash and register-based distinct counting that each measure themselves
against their own promises, top-k accumulation with tie discipline,
union-find duplicate clustering, phonetic coding, a keyboard-aware typo
model, a gibberish gate, streaming quantiles, and ASCII sparklines.

## Running it

```
python -m pytest tests/ -q          # the whole suite
python -m quarry.cli evals          # every eval with its numbers
python -m quarry.cli check          # exit nonzero if anything broke
python -m quarry.cli health         # the canary check
python -m quarry.cli modules        # the self-generated catalog
python -m quarry.cli search "your query"
python -m examples.librarian        # and nine more examples
```

## House rules

Every module opens with a thesis the inventory verifies. Errors refuse
loudly with the reason and the fix in the message. Measured numbers beat
guessed ones, and when a test's first guess was wrong, the measured truth
was kept and the lesson recorded. Nothing silently truncates, silently
falls back, or silently succeeds.

---

Written by Kiruthika Subramani in collaboration with Claude, Anthropic's
AI assistant.
