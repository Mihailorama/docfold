# docfold

Open-source Python document structuring toolkit. Published to PyPI as `docfold`.

> **Cross-workspace nav:** See parent `E:\GitHub\DatateraApp\CLAUDE.md` for full project map.

## Quick Start

```bash
pip install -e ".[dev]"       # Install with dev deps
pytest tests/                 # Run all tests
pytest tests/ -m "not slow"   # Skip slow tests
```

## Key Files

| File/Dir | Purpose |
|----------|---------|
| `docfold/` | Main package source |
| `tests/` | pytest test suite |
| `docs/conventions/golden-rules.md` | Rules you MUST follow |
| `docs/tasks/_TEMPLATE.md` | Feature proposal template |

## Golden Rules (Summary)

1. **Tests before implementation** - write failing tests first, then implement. See "Feature Development Workflow" below.
2. Never push to GitHub.
3. Preserve backward compatibility for the public API.
4. Test across all engines when modifying shared logic.

_Full rules: `docs/conventions/golden-rules.md`_

## Feature Development Workflow (TDD)

Every new feature or bugfix follows this 4-step process:

1. **Write a proposal** in `docs/tasks/FEATURE_NAME.md` (use `docs/tasks/_TEMPLATE.md`)
   - What problem does this solve? Why now?
   - Which engines/modules are affected?
   - Edge cases and failure modes

2. **Write failing tests first** (Red Phase)
   - Tests in `tests/` using pytest
   - Run: `pytest tests/` - confirm new tests FAIL

3. **Implement iteratively** (Green Phase)
   - Read the proposal + failing tests, implement in small chunks
   - Run tests after each chunk until all pass
   - Do not move on until all tests are GREEN

4. **Manual E2E verification**
   - Test with real documents across affected engines
   - Verify backward compatibility

This workflow is mandatory. See `docs/conventions/golden-rules.md` for the formal rule.
