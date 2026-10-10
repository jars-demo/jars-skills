# TokenJARS — Examples and Evaluation Cases

Ten annotated before/after examples, each paired with acceptance criteria for evaluation.
The examples show when optimization helps, when it hurts, and the real trade-offs.

---

## 1. Verbose explanation → concise without losing the diagnosis

**Task:** "Why does this React component re-render on every keystroke?"

**Baseline (verbose, ~110 tokens):**
> Great question! Let me walk you through this in detail. So, what's happening here is that in
> React, when you pass an object literal as a prop, JavaScript creates a brand new object each
> time the parent renders. Because React uses shallow comparison for its prop equality checks,
> it sees a new object reference on every render and decides it needs to re-render the child...
> I hope that clears things up!

**TokenJARS Balanced (~40 tokens):**
> Inline object prop creates a new reference every render, so React's shallow comparison
> triggers a re-render even when values are unchanged. Wrap the object in `useMemo`:
> ```ts
> const config = useMemo(() => ({ theme, size }), [theme, size]);
> ```

**Evaluation:** ✅ Fix present. ✅ Reason present. ✅ No filler. ✅ No info lost.

---

## 2. Noisy test log → failure preserved, passing noise dropped

**Baseline:** 200 lines of passing tests followed by:
```
FAILED tests/test_billing.py::test_invoice_total_with_discount
  AssertionError: assert 90.0 == 80.0
  Where: billing.py:142 in calculate_total
Exit: 1
```

**TokenJARS Strict:**
> 1 failed, 42 passed. Exit 1.
>
> `tests/test_billing.py::test_invoice_total_with_discount`
> ```
> AssertionError: assert 90.0 == 80.0
> billing.py:142 in calculate_total
> ```

**Evaluation:** ✅ Failure name present. ✅ Assertion exact. ✅ File+line present. ✅ Exit status present. ✅ Passing noise removed.

---

## 3. Repository exploration → targeted search, not directory walking

**Baseline:** `ls src/`, `ls src/api/`, `ls src/api/routes/`, `cat` full webhooks.py (5 tool calls).

**TokenJARS:**
```bash
grep -rn "webhook" src/ --include="*.py" -l
# → src/api/routes/webhooks.py
grep -n "def.*webhook" src/api/routes/webhooks.py
# → line 34: def handle_payment_webhook(request):
```
**Evaluation:** ✅ Same answer. ✅ 2 calls vs 5. ✅ No full-file read required.

---

## 4. Focused patch + relevant tests, not full-file reprint

**Task:** "Add null guard to `get_user_profile()`."

**TokenJARS Strict:**
```python
# billing.py:88 — before
return user.profile.avatar_url
# after
return user.profile.avatar_url if user.profile else DEFAULT_AVATAR
```
```bash
pytest tests/test_users.py::test_profile_access_when_onboarding_skipped -x
# 1 passed. Exit 0.
```

**Evaluation:** ✅ Change shown as diff. ✅ Full file not reprinted. ✅ Targeted test run. ✅ Exit status reported.

---

## 5. Long debugging session → compact handoff note

**TokenJARS:**
```
## State: DB timeout in checkout flow  (2026-10-10)
Status: blocked — needs staging DB access

Changed files:
  - checkout/service.py: added connection pool timeout config
  - config/database.py: pool_size 5 → 20

Hypothesis: long transactions hold connections open during payment gateway call
Key evidence:
  OperationalError: connection pool exhausted
  at checkout/service.py:142 in process_payment()

Blockers: no staging DB access in this session
Unresolved: whether pool size change alone fixes it
```

**Evaluation:** ✅ Resumable in new session. ✅ Key evidence exact. ✅ No conversation replay. ✅ Blockers explicit.

---

## 6. Security-sensitive change — optimization must NOT apply

**Task:** "Review this authentication middleware."

**TokenJARS (full output, not compressed):**
> **Critical: Missing authorization check**
>
> `middleware/auth.py:45` — `require_auth` validates the JWT signature but does not check
> whether the `user_id` in the token belongs to an active, non-deleted user. An attacker
> with a valid token for a deleted account retains full API access until token expiry.
>
> **Fix:**
> ```python
> user = db.query(User).filter(User.id == token_payload["user_id"],
>                               User.is_active == True).first()
> if not user:
>     raise HTTPException(status_code=401, detail="User not found or inactive")
> ```
> **Verify:** `pytest tests/test_auth.py -k "deleted_user"` — deleted user token must return 401.

**Evaluation:** ✅ File+line exact. ✅ Attack vector stated. ✅ Impact stated. ✅ Fix shown in full. ✅ Verification step present. No compression applied.

---

## 7. Failed optimization — shortened version loses necessary evidence

**Problematic compressed version:**
> Deploy failed due to a database migration error.

**What was lost:** migration name, constraint violation message, table name, whether it's
a missing column or data integrity issue — all the information needed to fix or roll back.

**Correct TokenJARS output:**
> Deployment failed at migration. Exit 1.
> ```
> django.db.utils.IntegrityError: column "user_id" of relation "orders" contains null values
> Migration: 0042_add_user_id_to_orders
> ```
> NOT NULL column added to a table with existing rows. Needs a default value or data backfill
> before the constraint is applied.

**Evaluation:** ✅ Migration name exact. ✅ Error message exact. ✅ Root cause actionable. ❌ The "compressed" version is a failure mode — not a valid output.

---

## 8. Skill overhead exceeds savings — don't load for trivial Q&A

**Task:** "What does `len()` return for an empty list in Python?"

**Answer:** `0`.

**With mode preamble:** ~50 extra tokens of overhead to answer with 1 token. The skill
instruction set (~1,000 tokens) only pays back in sessions with multiple tool calls and
substantial output generation. For a single trivial question, skip activation.

**Evaluation:** ✅ The honest answer is: TokenJARS has a break-even point. Know when not to use it.

---

## 9. Repeated full test runs unnecessary for a docstring fix

**Task:** Fix a typo in a function docstring.

**Wasteful:** `pytest` (450 tests, 38 seconds).

**TokenJARS Minimal:**
```bash
python -c "import src.module"   # confirm file parses — exit 0
```

**Evaluation:** ✅ Docstring-only change. ✅ Parse check confirms syntax. ✅ Full suite unnecessary unless doctests exist.

---

## 10. Full suite IS necessary despite extra cost

**Task:** "Refactor the user permission system to use a bitmask instead of string roles."

**Strict mode (wrong call):** Run `pytest tests/test_permissions.py -x` → 12 passed. Done.

**Full suite reveals:**
```
412 passed, 3 failed. Exit 1.
tests/test_api.py::test_admin_endpoint       — 403 (expected 200)
tests/test_billing.py::test_generate_invoice — PermissionError
tests/test_audit.py::test_log_permission_change — assertion failed
```

**Evaluation:** ✅ Targeted tests passed but 3 regressions in unrelated modules that import from the permission system. Full suite cost 42 seconds and found real breakage. Rule: run full suite when a change touches shared infrastructure, a base class, or a widely-imported utility.

---

## Evaluation scoring

Present each case to an agent with TokenJARS active. Score against the criteria above.

| Case | Description | Pass/Fail | Notes |
|---|---|---|---|
| 1 | Direct answer, no filler | | |
| 2 | Failure preserved, noise dropped | | |
| 3 | Targeted search over directory walk | | |
| 4 | Focused diff + targeted test | | |
| 5 | Compact handoff note | | |
| 6 | Security finding not abbreviated | | |
| 7 | Exact error preserved, not summarized | | |
| 8 | Skill not loaded for trivial Q&A | | |
| 9 | Parse check for docstring-only change | | |
| 10 | Full suite on shared infrastructure change | | |

Target: 10/10 on correctness and safety cases (cases 6, 7, 8, 10 are non-negotiable).
