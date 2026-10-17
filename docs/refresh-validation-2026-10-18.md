# 2026-10-18 refresh validation

Changes were developed in an isolated worktree. No live feed, generated
production output, scheduler, service, credential or provider was changed.

## Storage and pipeline

- Six independent Python processes concurrently append overlapping batches to
  a temporary JSONL. All 175 new IDs appear once; the original historical
  bytes remain an exact prefix. Duplicate IDs already in history remain.
- Invalid batch serialization or invalid existing JSON aborts without writing.
  A valid historical last line without a newline is separated before append.
- A metadata-fill process waits for a writer's sidecar lock and preserves the
  newly appended row after replacing the file. Classifier saves merge only
  derived fields into the latest feed, preserving concurrent promotions and
  source metadata filled while inference was running.
- Classifier merges match source/content plus duplicate occurrence, and apply
  only fields changed during this run. A fully cached duplicate-ID feed stays
  byte-for-byte unchanged. Concurrent classification or source-text edits are
  preserved instead of being overwritten by an older inference snapshot.
- Pipeline tests hold a lock with a year-2000 timestamp: it cannot be evicted
  by the old age threshold. Clean exit and SIGKILL release ownership while
  keeping the same inode. A live legacy PID lock is respected.
- A real stage subprocess inherits the lock. Killing its controller does not
  allow another pipeline until that stage exits. Runtime-status write failure
  also releases the controller's lock.
- All repository subprocess launches forward the lock descriptor and its marker.
  A synthetic executable launched through the real YouTube adapter keeps the
  lock after both controller and stage are killed; the lock becomes available
  only when that grandchild exits.

The locks coordinate cooperating processes on one local filesystem. They do
not make arbitrary direct writes or data-branch restores safe to run alongside
independent fetchers. Upgrade only after the previous pipeline and its
children have finished; never delete an active lock or run production without it.

## Homepage

The initial render uses 10 posts per column instead of 30, including the
mobile all-city fallback. Existing 400-post bundles, filters, deep links and
load-more logic remain. This limits initial DOM creation without discarding
collected posts or changing classification.

Synthetic fixture: six candidates, 75 posts each, fixed timestamps, local SVG
images and no external content fetches. Same input before/after:

| Metric | 30 per column | 10 per column |
| --- | ---: | ---: |
| Initial post cards | 210 | 70 |
| Decoded HTML bytes | 801,612 | 284,874 |
| Parsed HTML elements | 7,008 | 2,560 |

These are fixture size/DOM measurements, not production latency results.

T3 collaborative browser checks on a loopback-only fixture server:

- Desktop 1280×800: seven columns with 10 cards each, no page horizontal
  overflow, no failed local images. Load more preserved contiguous post IDs
  with no duplicates; the existing intersection observer may append another
  batch after scrolling to the button.
- Mobile 390×844: candidate deep link showed 10 posts from that candidate;
  `platform=website` included only matching posts; no page horizontal overflow.
- Injected feed-fetch failure showed an actionable retry. Restoring fetch and
  pressing Retry recovered 10 correct candidate posts.
- A sandboxed frame with scripts disabled retained the SSR cards and source
  directory link; only the all-city column was visible at mobile width.

## Repeatable checks

```sh
python3 -m unittest discover -s tests -v
find site/assets -type f -name '*.js' -print0 | xargs -0 -n 1 node --check
```

Result on the development Mac after review fixes: 93 tests passed; all nine JavaScript files
passed syntax checks. CI runs these on Python 3.11 and 3.13, with Node 24,
without installing ingestion dependencies or invoking the production pipeline.
The full suite also passed with audit hooks blocking network connections and
writes/deletions in this checkout's data, state, site and published trees.
Instagram error fixtures write into their temporary test directories.

For an isolated manual browser fixture:

```sh
python3 tests/home_fixture.py /tmp/mayor-home-fixture
python3 -m http.server --bind 127.0.0.1 --directory /tmp/mayor-home-fixture 8879
```

CI execution and production deployment have not been performed in this worktree.
