"""Evaluation runner — orchestrates benchmark runs across engines and datasets."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docfold.engines.base import EngineResult, OutputFormat
from docfold.engines.router import EngineRouter
from docfold.evaluation.metrics import compute_cer, compute_wer

logger = logging.getLogger(__name__)


@dataclass
class DocumentScore:
    """Scores for a single (engine, document) pair."""

    document_id: str
    engine_name: str
    category: str
    cer: float | None = None
    wer: float | None = None
    table_f1: float | None = None
    heading_f1: float | None = None
    reading_order: float | None = None
    processing_time_ms: int = 0
    error: str | None = None


@dataclass
class EvaluationReport:
    """Full evaluation report across all engines and documents."""

    timestamp: str = ""
    scores: list[DocumentScore] = field(default_factory=list)
    engine_summaries: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "scores": [vars(s) for s in self.scores],
            "engine_summaries": self.engine_summaries,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class EvaluationRunner:
    """Runs evaluation across engines and a ground-truth dataset.

    Usage::

        runner = EvaluationRunner(router, dataset_path="tests/evaluation/dataset")
        report = await runner.run(engines=["docling", "mineru"])
        print(report.to_json())
    """

    def __init__(self, router: EngineRouter, dataset_path: str) -> None:
        self.router = router
        self.dataset_path = Path(dataset_path)

    async def run(
        self,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> EvaluationReport:
        """Run the full evaluation.

        Args:
            engines: Engine names to evaluate (None = all available).
            categories: Document categories to include (None = all).
        """
        report = EvaluationReport(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        gt_files = self._discover_ground_truth(categories)
        logger.info("Found %d ground-truth documents", len(gt_files))

        available_engines = engines or [
            e["name"] for e in self.router.list_engines() if e["available"]
        ]

        for doc_path, gt_path in gt_files:
            gt = self._load_ground_truth(gt_path)

            for engine_name in available_engines:
                score = await self._evaluate_single(doc_path, gt, engine_name)
                report.scores.append(score)

        report.engine_summaries = self._compute_summaries(report.scores)
        return report

    async def _evaluate_single(
        self,
        doc_path: Path,
        ground_truth: dict[str, Any],
        engine_name: str,
    ) -> DocumentScore:
        doc_id = ground_truth.get("document_id", doc_path.stem)
        category = ground_truth.get("category", "unknown")

        try:
            result: EngineResult = await self.router.process(
                str(doc_path),
                output_format=OutputFormat.MARKDOWN,
                engine_hint=engine_name,
            )
        except Exception as e:
            return DocumentScore(
                document_id=doc_id,
                engine_name=engine_name,
                category=category,
                error=str(e),
            )

        gt_data = ground_truth.get("ground_truth", {})
        ref_text = gt_data.get("full_text", "")

        cer = compute_cer(result.content, ref_text) if ref_text else None
        wer = compute_wer(result.content, ref_text) if ref_text else None

        return DocumentScore(
            document_id=doc_id,
            engine_name=engine_name,
            category=category,
            cer=cer,
            wer=wer,
            processing_time_ms=result.processing_time_ms,
        )

    def _discover_ground_truth(
        self, categories: list[str] | None
    ) -> list[tuple[Path, Path]]:
        """Find (document, ground_truth.json) pairs in the dataset."""
        pairs = []
        for gt_file in self.dataset_path.rglob("*.ground_truth.json"):
            category = gt_file.parent.name
            if categories and category not in categories:
                continue

            stem = gt_file.name.replace(".ground_truth.json", "")
            # Find the matching document file
            for candidate in gt_file.parent.iterdir():
                if candidate.stem == stem and ".ground_truth" not in candidate.name:
                    pairs.append((candidate, gt_file))
                    break

        return pairs

    def _load_ground_truth(self, gt_path: Path) -> dict[str, Any]:
        return json.loads(gt_path.read_text(encoding="utf-8"))

    @staticmethod
    def _compute_summaries(scores: list[DocumentScore]) -> dict[str, dict[str, float]]:
        """Aggregate per-engine averages."""
        from collections import defaultdict

        engine_scores: dict[str, list[DocumentScore]] = defaultdict(list)
        for s in scores:
            if s.error is None:
                engine_scores[s.engine_name].append(s)

        summaries = {}
        for engine, sc_list in engine_scores.items():
            cers = [s.cer for s in sc_list if s.cer is not None]
            wers = [s.wer for s in sc_list if s.wer is not None]
            times = [s.processing_time_ms for s in sc_list]

            summaries[engine] = {
                "avg_cer": sum(cers) / len(cers) if cers else -1,
                "avg_wer": sum(wers) / len(wers) if wers else -1,
                "avg_time_ms": sum(times) / len(times) if times else -1,
                "documents_evaluated": len(sc_list),
            }

        return summaries
