# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial scaffold: extraction contract (`ExtractionEngine`, `ExtractionResult`,
  `ExtractionField`, `ExtractionCapabilities`, `load_schema`).
- `ExtractionRouter` with engine selection (hint / env default / priority /
  allowed-engines), fallback, batch, compare, and introspection.
- **Lift** engine adapter (`extractfold[lift]`) wrapping `lift-pdf`, with vLLM
  (default) and HuggingFace backends.
- Evaluation metrics: `field_accuracy` and `schema_compliance`.
- Unit test suite (no model weights required) and CI workflow.
