---
name: datetime-handling
description: Handling dates, times, and time zones without off-by-hours bugs. Stores instants in UTC with timezone-aware types, keeps future local events as wall time plus an IANA zone, serialises as ISO 8601 with an offset, converts to the user's zone only at display, handles DST gaps and overlaps, separates calendar dates from instants, uses a monotonic clock for durations, and injects the clock so tests freeze time. Use when you want to fix a timezone bug, store timestamps correctly, convert between time zones, handle daylight saving time, schedule something at a local time, parse or format ISO 8601, choose timestamptz vs timestamp, fix dates that are off by one day, compute durations or timeouts, or freeze time in tests.
---

## datetime-handling

An instant is a point on the global timeline. A wall time is what a clock on a wall shows.
Most time bugs come from mixing the two. Decide which one each value is, then store,
send, and compute it accordingly.

### Ground rules

- Follow the project's own conventions first: `CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`,
  and the date library already in use. Do not add a second date library.
- Changing a column type or the meaning of stored values is a data migration. Write it with
  the project's migration tooling, show the plan, and do not run it against a shared or
  production database unless the user asks.
- Never change the server, container, or database default time zone to "fix" a bug. Fix the
  code so it does not depend on it.
- Prove a fix with a test that fails before it, including a DST transition case.

---

### 1. Classify every time value

| Kind | Example | Store as | Never |
| --- | --- | --- | --- |
| **Instant** | `created_at`, `paid_at`, log time, token expiry | UTC, timezone-aware (`timestamptz`) | Naive local time |
| **Future local event** | "Meeting 09:00 in Berlin on 2027-03-29" | Local wall time + IANA zone (`Europe/Berlin`) | Pre-computed UTC only |
| **Calendar date** | Birthday, invoice date, holiday | `date` | Midnight timestamp |
| **Time of day** | "Store opens 09:00" | `time` + zone of the place | UTC time |
| **Duration** | Timeout, SLA, video length | Integer seconds/ms or ISO 8601 duration | Difference of wall-clock readings |

Why future local events keep the zone: governments change DST rules. If you store
"09:00 Berlin" as UTC today and the rules change, the meeting moves. Store the intent and
compute the instant when needed.

Use IANA zone names (`America/New_York`). Never store abbreviations (`EST`, `IST` is three
different zones) or fixed offsets (`+05:30`) as a user's zone: offsets change with DST.

---

### 2. Find the bugs

```bash
# Naive "now" and local-time calls
grep -rnE "datetime\.now\(\)|datetime\.utcnow\(|datetime\.today\(\)|date\.today\(\)|time\.localtime" --include=*.py .
grep -rnE "new Date\(\)\.get(Hours|Date|Day|Month|FullYear)\(|toLocaleString\(\)|moment\(" \
  --include=*.{js,ts,tsx} . | grep -v node_modules

# Parsing without a zone
grep -rnE "strptime\(|new Date\(['\"][0-9]{4}-[0-9]{2}-[0-9]{2}['\"]\)|Date\.parse\(" \
  --include=*.{py,js,ts,tsx} . | grep -v node_modules

# Zone-less columns
grep -rniE "timestamp without time zone|\btimestamp\b[^t]|DateTime\(\)|DateTimeField\(" \
  --include=*.{sql,py,ts,prisma} . | grep -v node_modules
```

Common culprits:

- Python `datetime.utcnow()` returns a **naive** value; it is deprecated since 3.12. Any
  later `.astimezone()` treats it as local time.
- JS `new Date('2026-03-01')` is UTC midnight, but `new Date('2026-03-01T00:00')` is local
  midnight. Same-looking strings, different instants.
- JS `getHours()`, `getDate()` read the **runtime's** zone, which differs between the
  server, CI, and each user's browser.

---

### 3. Store

PostgreSQL:

```sql
-- Instants: timestamptz stores UTC and converts on input/output
created_at  timestamptz NOT NULL DEFAULT now(),

-- Future local events: wall time + zone
starts_local  timestamp   NOT NULL,      -- 2027-03-29 09:00
starts_tz     text        NOT NULL,      -- 'Europe/Berlin'

-- Calendar dates
invoice_date  date        NOT NULL
```

- `timestamptz` does not store the zone; it stores UTC. Keep a separate zone column when
  you need to know where something happened.
- Pin the session zone for the app's connections to UTC so `timestamp` literals and
  `now()::date` behave the same everywhere: `SET TIME ZONE 'UTC'` or the driver option.
- MySQL `DATETIME` has no zone; `TIMESTAMP` converts via the session zone and ends in 2038.
  Store UTC in `DATETIME` with the connection zone set to `+00:00`.

ORMs: SQLAlchemy `DateTime(timezone=True)`, Django `USE_TZ = True`, Prisma `@db.Timestamptz`.

Migrating a `timestamp` column that holds UTC values to `timestamptz`:

```sql
ALTER TABLE orders
  ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
```

If the column actually holds server-local times, use that zone in `AT TIME ZONE` instead.
Check a few known rows first. This rewrites the table; on large tables plan it with the
project's zero-downtime migration process.

---

### 4. Create, parse, and serialise

Python (3.9+, `zoneinfo` in the standard library):

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

now = datetime.now(timezone.utc)                        # aware UTC instant
local = now.astimezone(ZoneInfo("Asia/Kolkata"))        # display only

# Parse: require an offset, reject naive input at the boundary
ts = datetime.fromisoformat("2026-10-24T09:30:00+05:30")
if ts.tzinfo is None:
    raise ValueError("timestamp must include a UTC offset")

# Serialise
ts.astimezone(timezone.utc).isoformat()                 # '2026-10-24T04:00:00+00:00'
```

TypeScript (built-in `Date` holds an instant; use `Intl` for zones):

```ts
const now = new Date();                                  // instant
now.toISOString();                                       // '2026-10-24T04:00:00.000Z'

// Display in the user's zone, never via getHours()
new Intl.DateTimeFormat('en-GB', {
  timeZone: user.timeZone,                               // 'Asia/Kolkata'
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(now);

// Validate API input carries an offset
const ISO_WITH_OFFSET = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
if (!ISO_WITH_OFFSET.test(input)) throw new ValidationError('timestamp must include Z or an offset');
```

For zone arithmetic in JS ("next Monday 09:00 in Berlin"), use the project's library
(`Temporal` where available, `luxon`, or `date-fns-tz`). `moment` is in maintenance mode;
do not add it to new code.

API contract:

- Send instants as ISO 8601 / RFC 3339 with `Z` or an offset. Not epoch numbers without a
  documented unit, not `"10/24/2026"`.
- Send calendar dates as `YYYY-MM-DD` and parse them as dates, not instants.
- Send the user's zone as an IANA name when the server must compute local times.

---

### 5. Convert to local time only at the edges

```
input (with offset) ─► UTC instant ─► store / compute / compare ─► user's zone ─► display
```

- Business logic compares and sorts instants in UTC.
- "Today", "this month", and "end of day" depend on a zone. Make it an explicit parameter:

```python
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

def start_of_day(day: date, tz: ZoneInfo) -> datetime:
    """Midnight of `day` in `tz`, as an aware datetime (convert to UTC for queries)."""
    return datetime.combine(day, time.min, tzinfo=tz)

# Orders placed "today" for a user in Los Angeles
tz = ZoneInfo(user.timezone)
today = datetime.now(tz).date()
start = start_of_day(today, tz).astimezone(timezone.utc)
end = start_of_day(today + timedelta(days=1), tz).astimezone(timezone.utc)
orders = repo.orders_between(start, end)   # created_at >= start AND created_at < end
```

Use half-open ranges (`>= start AND < end`). `BETWEEN ... AND '23:59:59'` drops the last
second and any sub-second values.

Off-by-one-day bugs usually mean a calendar date was turned into UTC midnight and then
displayed in a zone west of UTC. Keep it a `date` end to end.

---

### 6. DST gaps and overlaps

Twice a year a local time either does not exist (spring forward) or happens twice (fall back).

```python
from datetime import datetime
from zoneinfo import ZoneInfo

ny = ZoneInfo("America/New_York")

# Gap: 2026-03-08 02:30 does not exist in New York
datetime(2026, 3, 8, 2, 30, tzinfo=ny)          # Python does not raise; pick a policy

# Overlap: 2026-11-01 01:30 happens twice; fold selects which
first  = datetime(2026, 11, 1, 1, 30, tzinfo=ny, fold=0)   # EDT, UTC-4
second = datetime(2026, 11, 1, 1, 30, tzinfo=ny, fold=1)   # EST, UTC-5
```

Decide and document a policy for scheduled local events:

- **Gap**: run at the next valid time (03:00), the common choice for alarms and jobs.
- **Overlap**: run once, at the first occurrence (`fold=0`).

Adding time:

- "In 24 hours" is instant arithmetic: add to the UTC value.
- "Same time tomorrow" is wall-time arithmetic: add a day to the local date, keep the wall
  time, then resolve with the zone. Across a DST change these differ by an hour.

Cron and schedulers: run the scheduler in UTC, or use one that accepts an IANA zone per
job. A job at 02:30 local is skipped or doubled on transition days.

---

### 7. Durations and timeouts use a monotonic clock

Wall clocks jump (NTP sync, manual changes, leap smearing). Never measure elapsed time with
them.

```python
import time
start = time.monotonic()
do_work()
elapsed = time.monotonic() - start      # not datetime.now() - start
```

```ts
const start = performance.now();
await doWork();
const elapsedMs = performance.now() - start;   // not Date.now() - start
```

Go: `time.Since(start)` already uses the monotonic reading. Java: `System.nanoTime()` or
`Instant` plus `Duration` for wall-clock instants.

---

### 8. Inject the clock and test the hard dates

Code that calls `now()` directly cannot be tested deterministically. Pass a clock.

```python
from typing import Callable

Clock = Callable[[], datetime]

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class TokenService:
    def __init__(self, clock: Clock = utc_now):
        self._clock = clock

    def is_expired(self, token) -> bool:
        return self._clock() >= token.expires_at
```

```python
import pytest

@pytest.mark.parametrize("now, tz, expected_day", [
    (datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc), "America/New_York", date(2026, 3, 8)),   # DST start
    (datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc), "America/New_York", date(2026, 11, 1)), # DST end
    (datetime(2026, 12, 31, 20, 0, tzinfo=timezone.utc), "Asia/Kolkata", date(2027, 1, 1)),     # year rollover
    (datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc), "UTC", date(2028, 2, 29)),              # leap day
])
def test_local_day_for_user_uses_user_zone(now, tz, expected_day):
    assert local_day(now, ZoneInfo(tz)) == expected_day
```

JS: `vi.useFakeTimers(); vi.setSystemTime(new Date('2026-03-08T07:30:00Z'))` (or the Jest
equivalent), and restore in `afterEach`.

Run the suite once with a non-UTC zone to expose hidden dependencies on the runtime zone:

```bash
TZ=America/Los_Angeles pytest
TZ=Pacific/Chatham npm test   # +12:45/+13:45, catches code that assumes whole-hour offsets
```

Keep the tz database current: the `tzdata` package in Python on systems without one
(Windows, slim images), the OS `tzdata` package in containers, and an up-to-date Node.js
runtime for `Intl`.

---

### Examples

| Weak | Strong |
| --- | --- |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` |
| `created_at timestamp` | `created_at timestamptz` |
| Meeting stored as UTC only | Wall time `09:00` + `Europe/Berlin`, instant computed when needed |
| `user.tz = "+05:30"` or `"IST"` | `user.tz = "Asia/Kolkata"` |
| `date.getHours()` on the server | `Intl.DateTimeFormat` with an explicit `timeZone` |
| Birthday stored as `1990-05-01T00:00:00Z` | Birthday stored as `date '1990-05-01'` |
| `WHERE created_at BETWEEN '2026-10-01' AND '2026-10-31 23:59:59'` | `>= '2026-10-01' AND < '2026-11-01'` in the user's zone |
| `elapsed = Date.now() - start` | `performance.now() - start` |
| Server TZ changed to fix a report | Report takes the zone as a parameter |

### Rules

- Classify each value: instant, future local event, calendar date, time of day, or duration.
- Instants are timezone-aware and stored in UTC. Naive datetimes do not cross a boundary.
- Future local events keep wall time plus an IANA zone.
- Serialise instants as ISO 8601 with `Z` or an offset; reject input without one.
- Convert to a user's zone only for display or for zone-dependent queries, with the zone
  passed explicitly.
- Decide the DST gap and overlap policy and test both transitions.
- Measure durations with a monotonic clock.
- Inject the clock; test DST, year rollover, leap day, and a non-UTC `TZ`.
