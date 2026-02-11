"""Tests for the base engine interface and EngineResult dataclass."""

import pytest
from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat


class TestOutputFormat:
    def test_values(self):
        assert OutputFormat.MARKDOWN == "markdown"
        assert OutputFormat.HTML == "html"
        assert OutputFormat.JSON == "json"
        assert OutputFormat.TEXT == "text"

    def test_from_string(self):
        assert OutputFormat("markdown") == OutputFormat.MARKDOWN
        assert OutputFormat("html") == OutputFormat.HTML


class TestEngineResult:
    def test_minimal_creation(self):
        result = EngineResult(
            content="# Hello",
            format=OutputFormat.MARKDOWN,
            engine_name="test",
        )
        assert result.content == "# Hello"
        assert result.format == OutputFormat.MARKDOWN
        assert result.engine_name == "test"
        assert result.metadata == {}
        assert result.pages is None
        assert result.images is None
        assert result.confidence is None
        assert result.processing_time_ms == 0

    def test_full_creation(self):
        result = EngineResult(
            content="<h1>Hello</h1>",
            format=OutputFormat.HTML,
            engine_name="docling",
            metadata={"pipeline": "standard"},
            pages=5,
            images={"img1.png": "base64data"},
            tables=[{"col1": "val1"}],
            confidence=0.95,
            processing_time_ms=1234,
        )
        assert result.pages == 5
        assert result.confidence == 0.95
        assert "img1.png" in result.images


class TestDocumentEngineInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DocumentEngine()  # type: ignore

    def test_concrete_implementation(self):
        class DummyEngine(DocumentEngine):
            @property
            def name(self) -> str:
                return "dummy"

            @property
            def supported_extensions(self) -> set[str]:
                return {"txt"}

            async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
                return EngineResult(
                    content="dummy",
                    format=output_format,
                    engine_name=self.name,
                )

            def is_available(self) -> bool:
                return True

        engine = DummyEngine()
        assert engine.name == "dummy"
        assert engine.is_available()
        assert "txt" in engine.supported_extensions
        assert repr(engine) == "<DummyEngine name='dummy' available=True>"
