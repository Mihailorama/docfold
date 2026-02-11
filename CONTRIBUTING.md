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
