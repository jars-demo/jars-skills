# The lab

`lab/` is the heart of the workshop. Learners break nothing: the bugs are already there, and the
checks tell them when a fix is real.

## Pick the lab type

- **The topic is a tool** (Docker, Postgres, Redis, Kubernetes, Git and so on): the lab drives
  the real tool and its checks use the real tool. Never simulate the tool. Go from beginner to
  advanced use. Solutions live in `lab/solutions/`.
- **Anything else:** Python 3.13 with `uv` and the standard library only. `pytest` and `ruff` are
  the only dev dependencies. Use real sockets, HTTP and SQLite where they make it real.
  Solutions live in `lab/tests/solutions/`.

## Cases

- One case per chapter. Each has exactly ONE deliberate bug that teams really hit.
- Real engineering only: real services, users (`u_1041`), events, APIs, databases and providers.
- **Deterministic.** Same symptom on every run, on any OS. Use fake clocks, barriers, events,
  seeded randomness and scripted faults. Never rely on lucky timing or sleeps.
- The shipped code is the buggy code. The learner edits it in place.

## CLI

```bash
uv run python -m <pkg> list           # every case, its level and one-line symptom
uv run python -m <pkg> run N          # prints the real symptom in concrete numbers
uv run python -m <pkg> check N        # labelled PASS / FAIL lines, non-zero exit on any FAIL
uv run python -m <pkg> hint N         # three steps, from a nudge to almost the answer
uv run python -m <pkg> try <name>     # an experiment that measures and prints a table
```

## Checks

- Check the real goal, not the code's shape. The lazy non-fix must fail: turning the feature
  off, catching and hiding the error, or special-casing the test input.
- Each PASS or FAIL line names what it checked, for example
  `FAIL  u_1041 got 2 emails for evt_88 (want 1)`.

## Tests

- Every case fails as shipped.
- Every case passes with its solution applied.
- A wrong-fixes test applies 1 or 2 plausible wrong fixes per case and proves the check rejects
  them, and applies one valid alternative fix and proves it passes.
- Tests restore the shipped code afterwards, so they can run in any order.

## Experiments

Write 3 or 4 `try` experiments that MEASURE real things on this machine (latency, throughput,
retries, bytes, lock waits) and print tables. The site and chapters quote their real output.

## Cleanup and safety

- Name everything the lab creates after the lab: containers, networks, volumes, temp dirs, DB
  files. Clean it up at the end of every command and test.
- Bind servers to `127.0.0.1` and pick ports the lab owns. Never touch anything else.
- Security topics: attacks target only the lab's own service. No scanning, no outside hosts, no
  payloads aimed at real software. Prove the bug, then spend the depth on the fix, detection
  and logging.
