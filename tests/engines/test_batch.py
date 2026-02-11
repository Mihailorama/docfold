"""Tests for batch processing and progress callbacks."""

import pytest
from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import BatchResult, EngineRouter


class FakeEngine(DocumentEngine):
    def __init__(self, name="fake", extensions=None, fail_on=None):
        self._name = name
        self._extensions = extensions or {"pdf", "docx"}
        self._fail_on = fail_on or set()

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_extensions(self) -> set[str]:
        return self._extensions

    def is_available(self) -> bool:
        return True

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        if file_path in self._fail_on:
            raise RuntimeError(f"Simulated failure on {file_path}")
        return EngineResult(
            content=f"content of {file_path}",
            format=output_format,
            engine_name=self._name,
            processing_time_ms=10,
        )


@pytest.fixture
def router():
    return EngineRouter([FakeEngine()])


class TestBatchResult:
    def test_defaults(self):
        b = BatchResult()
        assert b.total == 0
        assert b.succeeded == 0
        assert b.failed == 0
        assert b.results == {}
        assert b.errors == {}
        assert b.total_time_ms == 0

    def test_success_rate_zero_total(self):
        assert BatchResult().success_rate == 0.0

    def test_success_rate_computed(self):
        b = BatchResult(total=10, succeeded=7, failed=3)
        assert b.success_rate == 0.7


class TestProcessBatch:
    @pytest.mark.asyncio
    async def test_all_succeed(self, router):
        batch = await router.process_batch(["a.pdf", "b.pdf", "c.pdf"])
        assert batch.total == 3
        assert batch.succeeded == 3
        assert batch.failed == 0
        assert len(batch.results) == 3
        assert len(batch.errors) == 0
        assert batch.total_time_ms >= 0
        assert "a.pdf" in batch.results
        assert batch.results["a.pdf"].content == "content of a.pdf"

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        engine = FakeEngine(fail_on={"bad.pdf"})
        router = EngineRouter([engine])
        batch = await router.process_batch(["good.pdf", "bad.pdf", "ok.pdf"])
        assert batch.total == 3
        assert batch.succeeded == 2
        assert batch.failed == 1
        assert "good.pdf" in batch.results
        assert "bad.pdf" in batch.errors
        assert "Simulated failure" in batch.errors["bad.pdf"]

    @pytest.mark.asyncio
    async def test_all_fail(self):
        engine = FakeEngine(fail_on={"a.pdf", "b.pdf"})
        router = EngineRouter([engine])
        batch = await router.process_batch(["a.pdf", "b.pdf"])
        assert batch.succeeded == 0
        assert batch.failed == 2

    @pytest.mark.asyncio
    async def test_empty_list(self, router):
        batch = await router.process_batch([])
        assert batch.total == 0
        assert batch.succeeded == 0

    @pytest.mark.asyncio
    async def test_concurrency_respected(self, router):
        # Just verify it doesn't crash with concurrency=1
        batch = await router.process_batch(["a.pdf", "b.pdf", "c.pdf"], concurrency=1)
        assert batch.succeeded == 3

    @pytest.mark.asyncio
    async def test_engine_hint(self):
        engine_a = FakeEngine(name="alpha")
        engine_b = FakeEngine(name="beta")
        router = EngineRouter([engine_a, engine_b])
        batch = await router.process_batch(["x.pdf"], engine_hint="beta")
        assert batch.results["x.pdf"].engine_name == "beta"

    @pytest.mark.asyncio
    async def test_output_format_passed(self, router):
        batch = await router.process_batch(["x.pdf"], output_format=OutputFormat.HTML)
        assert batch.results["x.pdf"].format == OutputFormat.HTML


class TestProgressCallback:
    @pytest.mark.asyncio
    async def test_callback_called(self, router):
        events = []

        def on_progress(*, current, total, file_path, engine_name, status, **_):
            events.append({"current": current, "status": status, "file": file_path})

        await router.process_batch(["a.pdf", "b.pdf"], on_progress=on_progress)

        # Each file gets "processing" + "completed" = 2 events per file
        statuses = [e["status"] for e in events]
        assert statuses.count("processing") == 2
        assert statuses.count("completed") == 2

    @pytest.mark.asyncio
    async def test_callback_receives_result_on_complete(self, router):
        results_received = []

        def on_progress(*, status, result, **_):
            if status == "completed":
                results_received.append(result)

        await router.process_batch(["a.pdf"], on_progress=on_progress)
        assert len(results_received) == 1
        assert results_received[0].engine_name == "fake"

    @pytest.mark.asyncio
    async def test_callback_on_failure(self):
        engine = FakeEngine(fail_on={"fail.pdf"})
        router = EngineRouter([engine])
        errors_received = []

        def on_progress(*, status, error, **_):
            if status == "failed":
                errors_received.append(error)

        await router.process_batch(["fail.pdf"], on_progress=on_progress)
        assert len(errors_received) == 1
        assert errors_received[0] is not None
