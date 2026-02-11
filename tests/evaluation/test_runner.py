"""Tests for the evaluation runner."""

import json
import os
import tempfile
import pytest
from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter
from docfold.evaluation.runner import EvaluationRunner, EvaluationReport, DocumentScore


class StubEngine(DocumentEngine):
    @property
    def name(self) -> str:
        return "stub"

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf", "txt"}

    def is_available(self) -> bool:
        return True

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        return EngineResult(
            content="Hello world extracted text",
            format=output_format,
            engine_name=self.name,
            processing_time_ms=42,
        )


class TestDocumentScore:
    def test_creation(self):
        s = DocumentScore(
            document_id="doc1",
            engine_name="test",
            category="invoice",
            cer=0.05,
            wer=0.10,
        )
        assert s.document_id == "doc1"
        assert s.cer == 0.05
        assert s.error is None


class TestEvaluationReport:
    def test_to_dict(self):
        report = EvaluationReport(timestamp="2026-01-01T00:00:00")
        d = report.to_dict()
        assert d["timestamp"] == "2026-01-01T00:00:00"
        assert d["scores"] == []

    def test_to_json(self):
        report = EvaluationReport(timestamp="2026-01-01")
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["timestamp"] == "2026-01-01"

    def test_with_scores(self):
        report = EvaluationReport(
            scores=[
                DocumentScore("d1", "eng1", "invoice", cer=0.05),
                DocumentScore("d2", "eng1", "invoice", cer=0.03),
            ]
        )
        d = report.to_dict()
        assert len(d["scores"]) == 2


class TestEvaluationRunner:
    @pytest.fixture
    def dataset_dir(self, tmp_path):
        """Create a minimal evaluation dataset."""
        cat_dir = tmp_path / "invoices"
        cat_dir.mkdir()

        # Create a dummy document
        doc = cat_dir / "inv_001.txt"
        doc.write_text("Hello world extracted text")

        # Create ground truth
        gt = cat_dir / "inv_001.ground_truth.json"
        gt.write_text(json.dumps({
            "document_id": "inv_001",
            "category": "invoice",
            "ground_truth": {
                "full_text": "Hello world extracted text",
            }
        }))

        return tmp_path

    @pytest.fixture
    def runner(self, dataset_dir):
        router = EngineRouter([StubEngine()])
        return EvaluationRunner(router, dataset_path=str(dataset_dir))

    @pytest.mark.asyncio
    async def test_run_produces_report(self, runner):
        report = await runner.run()
        assert isinstance(report, EvaluationReport)
        assert len(report.scores) == 1
        assert report.scores[0].engine_name == "stub"
        assert report.scores[0].document_id == "inv_001"

    @pytest.mark.asyncio
    async def test_perfect_match_scores(self, runner):
        report = await runner.run()
        score = report.scores[0]
        assert score.cer == 0.0
        assert score.wer == 0.0
        assert score.error is None

    @pytest.mark.asyncio
    async def test_engine_summaries(self, runner):
        report = await runner.run()
        assert "stub" in report.engine_summaries
        summary = report.engine_summaries["stub"]
        assert summary["avg_cer"] == 0.0
        assert summary["documents_evaluated"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_category(self, runner):
        report = await runner.run(categories=["nonexistent"])
        assert len(report.scores) == 0

    @pytest.mark.asyncio
    async def test_filter_by_engine(self, runner):
        report = await runner.run(engines=["nonexistent"])
        # Scores are created but with an error since the engine doesn't exist
        assert len(report.scores) == 1
        assert report.scores[0].error is not None
        assert "nonexistent" in report.scores[0].error

    @pytest.mark.asyncio
    async def test_empty_dataset(self, tmp_path):
        router = EngineRouter([StubEngine()])
        runner = EvaluationRunner(router, dataset_path=str(tmp_path))
        report = await runner.run()
        assert len(report.scores) == 0
