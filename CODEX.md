# CODEX.md

## Setup
pip install -e ".[dev]"

## Test
pytest tests/

## Rules
- Follow TDD: write failing tests before implementation code
- Create a proposal in docs/tasks/FEATURE_NAME.md before coding
- Run tests and confirm they FAIL before writing implementation
- Run tests after each implementation chunk until all pass
- Never skip tests. Never merge without green tests
- Preserve backward compatibility for public API
- Test across all engines when modifying shared logic
- Deliver through a GitHub pull request; agents may push branches and merge green PRs. Never push directly to main, and never create a v* tag or start a release without the owner's explicit approval
- See docs/conventions/golden-rules.md for full rules
