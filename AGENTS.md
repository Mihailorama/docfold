# Repository Guidelines

## Project Structure
- `docfold/` - main package source
- `tests/` - pytest tests mirroring package structure
- `docs/` - documentation and conventions

## Build, Test, and Development Commands
- `pip install -e ".[dev]"` - install with dev dependencies
- `pytest tests/` - run all tests
- `pytest tests/ -m "not slow"` - skip slow integration tests

## Coding Style
- PEP 8, 4-space indentation, type hints on public API
- Use `loguru.logger` for logging
- Async functions with `async def` for I/O operations

## Feature Development Workflow (TDD - MANDATORY)

This repository enforces Test-Driven Development. Every feature or fix MUST follow this sequence:

### Step 1: Proposal
Create `docs/tasks/FEATURE_NAME.md` using the template at `docs/tasks/_TEMPLATE.md`.
Define: problem, solution, affected files, test plan, edge cases.

### Step 2: Failing Tests (Red Phase)
Write tests in `tests/` using pytest.
Run `pytest tests/` - new tests MUST fail (no implementation yet).
If tests pass without implementation, they are testing nothing useful.

### Step 3: Implementation (Green Phase)
Implement code to make failing tests pass. Run tests after every change.
Stop when all tests are green.

### Step 4: E2E Verification
Test with real documents. Verify backward compatibility.

### Anti-patterns
- Writing implementation before tests
- Writing tests that pass immediately (they test nothing)
- Skipping the proposal step for non-trivial features
- Merging without green tests

## Durable lessons and owner corrections

- Before finishing substantial work, check whether a recurring mistake, a verified workaround, or an owner correction yields a reusable rule.
- Check existing instructions and skills first. Update the matching rule in place, reconcile contradictions, and avoid duplicate or single-session skills.
- Keep project-specific guidance in this repository; put a reusable workflow in the existing relevant skill. Keep shared policies in AGENTS.md and make them available to Claude Code through CLAUDE.md.
- Turn a fixed behavioral bug into the smallest meaningful regression check, reusing the existing tests or evals. Instruction-only edits need a diff and consistency review, not an artificial test suite.
- Record verified guidance and when it applies. Keep secrets and private client material out of shared instructions and global skills; preserve existing access, approval, and data-storage boundaries.

## Shared instruction alignment

Read this AGENTS.md and the project guidance in [CLAUDE.md](CLAUDE.md) once before working. Shared policies apply to every agent; commands, models, and tools explicitly tied to one runtime apply only to that runtime. CLAUDE.md imports AGENTS.md so both agents receive the same shared rules. When changing a shared policy, update its existing source and reconcile the counterpart in the same change. Do not recursively reload these files.
