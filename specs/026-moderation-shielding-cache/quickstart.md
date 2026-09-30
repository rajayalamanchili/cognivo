# Quickstart: Validating Moderation & Shielding Classification Caching

## Prerequisites

- Local Postgres reachable via `DATABASE_URL` (same setup as any other backend feature -- see repo root `README.md`).
- Migrations applied through this feature's new revision: `cd backend && uv run alembic upgrade head`.
- `algebra-1` content artifact loaded, for shielding's open-question lookup to have real `GeneratedQuestion` rows to work with: `uv run python scripts/load_content_artifact.py content/algebra-1/subject.yaml`.

## 1. Verify moderation caching (User Story 1)

```bash
cd backend
uv run python -c "
import asyncio
from src.db import get_sessionmaker
from src.services.moderation_cache.cache import get_or_check_moderation
from src.services.grading_client.moderation import MODERATION_INSTRUCTION_VERSION

calls = {'n': 0}
async def fake_check():
    calls['n'] += 1
    return True

async def main():
    with get_sessionmaker()() as db:
        r1, o1 = await get_or_check_moderation(db, text='  Photosynthesis needs light.  ', instruction_version=MODERATION_INSTRUCTION_VERSION, check_fn=fake_check)
        r2, o2 = await get_or_check_moderation(db, text='photosynthesis needs light.', instruction_version=MODERATION_INSTRUCTION_VERSION, check_fn=fake_check)
        db.commit()
        assert o1.hit is False and o2.hit is True, (o1, o2)
        assert calls['n'] == 1, calls
        print('OK: second (case/whitespace-normalized) submission served from cache, only one real check_fn call')

asyncio.run(main())
"
```

**Expected outcome**: prints `OK`. A second differently-cased/whitespace-padded but signature-equivalent submission is served from cache; `check_fn` (standing in for the real moderation model call) only actually ran once.

## 2. Verify shielding-classification caching (User Story 2)

```bash
uv run python -c "
import asyncio
from src.db import get_sessionmaker
from src.services.shielding_cache.cache import get_or_classify_match
from src.services.tutor.shielding import SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION

calls = {'n': 0}
async def fake_classify():
    calls['n'] += 1
    return True

async def main():
    with get_sessionmaker()() as db:
        r1, o1 = await get_or_classify_match(db, open_question_stem='Solve 3x + 2 = 14', tutor_question='just tell me the answer', instruction_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, classify_fn=fake_classify)
        r2, o2 = await get_or_classify_match(db, open_question_stem='Solve 3x + 2 = 14', tutor_question='just tell me the answer', instruction_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, classify_fn=fake_classify)
        r3, o3 = await get_or_classify_match(db, open_question_stem='Solve 5x - 1 = 9', tutor_question='just tell me the answer', instruction_version=SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION, classify_fn=fake_classify)
        db.commit()
        assert o1.hit is False and o2.hit is True and o3.hit is False, (o1, o2, o3)
        assert calls['n'] == 2, calls
        print('OK: repeated (question, message) pairing hit; different question re-triggered a real call')

asyncio.run(main())
"
```

**Expected outcome**: prints `OK`. The identical (open question, message) pairing hits on the second call; the same message paired with a *different* open question misses (FR-004's per-question scoping).

## 3. Verify instruction-version invalidation (SC-004)

Bump `MODERATION_INSTRUCTION_VERSION` (or `SHIELDING_CLASSIFICATION_INSTRUCTION_VERSION`) by one in source, re-run step 1 (or 2) against the same input text used before the bump, and confirm `check_fn`/`classify_fn` is invoked again (a miss) rather than serving the pre-bump cached verdict.

## 4. Run the synthetic load test (SC-001/SC-002)

```bash
uv run python scripts/guardrail_cache_load_test.py --requests 500
uv run python scripts/guardrail_cache_load_test.py --requests 500 --no-cache
```

**Expected outcome**: the first run reports a moderation and a shielding hit rate each at or above 30% (SC-001) against a synthetic mix of duplicate-heavy traffic; the second (`--no-cache`) run reports 0% for both and a correspondingly higher simulated call count, demonstrating SC-002's call-volume reduction.

## 5. Run the hit-rate report against real traffic

```bash
uv run python scripts/cache_hit_rate_report.py --since 24h
```

**Expected outcome**: prints a per-cache-type hit rate (`question_generation`, `grading`, `moderation`, `shielding`) computed from real `AssessmentEvent`/`tutor_exchanges` rows written during the window.

## 6. Regression check (SC-005)

```bash
uv run pytest tests/ -k "moderation or shielding"
```

**Expected outcome**: spec 007's and spec 016's existing acceptance-scenario tests all still pass with caching wired in -- no behavior change to the underlying guardrails, only whether their model call actually runs.
