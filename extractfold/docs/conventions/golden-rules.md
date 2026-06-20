# Golden Rules

Inherited from docfold — extractfold follows the same discipline.

1. **Tests before implementation.** Write failing tests first (Red), then
   implement until green (Green). Every feature/bugfix starts with a proposal in
   `docs/tasks/` using `docs/tasks/_TEMPLATE.md`.
2. **Preserve backward compatibility** for the public API
   (`ExtractionEngine`, `ExtractionResult`, `ExtractionRouter`, engine names).
3. **Test across all engines** when modifying shared logic (the contract, the
   router, evaluation).
4. **Engines are optional extras.** Heavy dependencies (torch, model packages)
   live behind `extractfold[<engine>]` and must never be imported at module top
   level — import lazily inside methods so the core stays dependency-free.
5. **Unit tests must not require model weights.** Stub engine packages (see
   `tests/engines/test_lift_engine.py`); gate real runs behind the
   `integration` marker.

## Feature Development Workflow (TDD)

1. Write a proposal in `docs/tasks/FEATURE_NAME.md`.
2. Write failing tests in `tests/`; confirm they FAIL.
3. Implement in small chunks until all tests are GREEN.
4. Manual E2E verification across affected engines.
