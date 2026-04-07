---
purpose: "Non-negotiable engineering rules for AI and humans working in this repository"
updated: "2026-04-07"
---

# Golden Rules

These rules are absolute. AI agents must follow them without exception.

---

### Rule: Tests before implementation
- **What:** Write functional tests BEFORE writing implementation code. Tests must fail first (Red Phase), then pass after implementation (Green Phase). Follow the 4-step workflow: proposal -> failing tests -> iterative implementation -> e2e verification.
- **Why:** docfold is a published PyPI library. Breaking changes affect downstream users (ai-utils, data-paladin). TDD catches regressions early and ensures the public API surface is tested.
- **Example (do):**
  1. Write `tests/test_new_engine.py` with tests for the new engine
  2. Run `pytest tests/` - confirm failures
  3. Implement the engine
  4. Run `pytest tests/` - confirm all pass
- **Example (don't):** Write the full implementation first, then write tests that merely assert the current behavior.
- **Workflow:** See `CLAUDE.md` -> "Feature Development Workflow (TDD)" and `docs/tasks/_TEMPLATE.md`

### Rule: Never push to GitHub
- **What:** Never run `git push`. Code must be reviewed before reaching remote.
- **Why:** Pushing untested code can trigger a broken PyPI release.

### Rule: Preserve backward compatibility
- **What:** Never remove or rename public API functions/classes without a deprecation period.
- **Why:** docfold is a published library. Breaking changes affect ai-utils and other consumers.

### Rule: Test all engines
- **What:** When modifying shared OCR/extraction logic, run tests across all engines, not just the one you're changing.
- **Why:** Engines share code paths. A fix for one engine can break another.
