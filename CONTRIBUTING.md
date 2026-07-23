# Contributing to Docfold

Thanks for your interest in contributing! This document explains how to get started.

## Development Setup

```bash
git clone https://github.com/mihailorama/docfold.git
cd docfold
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                      # all tests
pytest tests/ -v            # verbose
pytest -k "test_router"     # filter by name
pytest --cov=docfold        # with coverage report
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/ tests/      # lint
ruff format src/ tests/     # format
mypy src/                   # type check
```

## Adding a New Engine Adapter

1. Create `src/docfold/engines/your_engine.py`
2. Subclass `DocumentEngine` and implement `name`, `supported_extensions`, `is_available()`, and `process()`
3. Add an optional dependency group in `pyproject.toml`
4. Register the engine in `cli.py` → `_build_router()`
5. Add tests in `tests/engines/test_adapters.py`
6. Update `README.md` supported engines table

## Adding Evaluation Metrics

1. Add the function to `src/docfold/evaluation/metrics.py`
2. Add tests in `tests/evaluation/test_metrics.py`
3. Wire it into `EvaluationRunner._evaluate_single()` if it uses ground truth data
4. Update `README.md` metrics table

## Contributing Ground Truth Data

Ground truth annotations are valuable. To contribute:

1. Place the source document in `tests/fixtures/golden/<category>/`
2. Create a `<filename>.ground_truth.json` alongside it following the schema in `docs/evaluation.md`
3. Keep files small (< 1 MB per document)

## Release Checklist

1. Bump `__version__` in `src/docfold/__init__.py` — the single source of
   truth; `pyproject.toml` reads it via hatch's dynamic version.
2. Move the `## [Unreleased]` entries in `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading.
3. Run the full gate locally: `ruff check src/ tests/`, `mypy src/`,
   `pytest tests/` — all clean. Re-run `pip install -e .` first so package
   metadata matches `__version__`.
4. Merge to `main`, then tag the release commit `vX.Y.Z` and push the tag —
   the `v*` tag build in `ci.yml` publishes to PyPI via trusted publishing.
   - If you cannot push tags directly (e.g. from an agent environment),
     dispatch the **Tag release** workflow
     (`.github/workflows/tag-release.yml`) with `tag: vX.Y.Z`; it verifies
     the tag matches `__version__` and pushes it. A tag pushed by that
     workflow's `GITHUB_TOKEN` does **not** trigger CI automatically —
     follow up with `gh workflow run ci.yml --ref vX.Y.Z`.
5. Verify: PyPI shows the new version and the GitHub Pages landing
   (served from `docs/` on `main`) redeployed.

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Ensure `pytest` and `ruff check` pass
4. Submit a PR with a clear description of what and why

## Reporting Issues

Open a GitHub issue with:
- What you expected vs. what happened
- Minimal reproducible example
- Python version and OS
- Installed extras (`pip list | grep docfold`)
