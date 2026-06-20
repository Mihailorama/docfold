"""Tests for the core extraction contract."""

import json

import pytest

from extractfold.engines.base import (
    ExtractionCapabilities,
    ExtractionEngine,
    ExtractionField,
    ExtractionResult,
    load_schema,
)


class TestLoadSchema:
    def test_dict_passthrough(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        assert load_schema(schema) is schema

    def test_json_string(self):
        assert load_schema('{"type": "object"}') == {"type": "object"}

    def test_file_path(self, tmp_path):
        p = tmp_path / "schema.json"
        p.write_text(json.dumps({"type": "object", "title": "x"}))
        assert load_schema(str(p)) == {"type": "object", "title": "x"}

    def test_named_reference(self):
        assert load_schema("invoice") == {"$ref": "invoice"}

    def test_invalid_type(self):
        with pytest.raises(TypeError):
            load_schema(123)  # type: ignore[arg-type]


class TestExtractionResult:
    def test_required_fields(self):
        r = ExtractionResult(data={"a": 1}, engine_name="lift")
        assert r.data == {"a": 1}
        assert r.engine_name == "lift"
        assert r.valid is None
        assert r.metadata == {}

    def test_to_dict_omits_optional_none(self):
        r = ExtractionResult(data={"a": 1}, engine_name="lift")
        d = r.to_dict()
        assert d["data"] == {"a": 1}
        assert "field_confidence" not in d
        assert "provenance" not in d

    def test_to_dict_includes_provenance(self):
        r = ExtractionResult(
            data={"total": 10},
            engine_name="lift",
            field_confidence={"total": 0.91},
            provenance={"total": ExtractionField(value=10, page=1, bbox=[0, 0, 1, 1])},
        )
        d = r.to_dict()
        assert d["field_confidence"] == {"total": 0.91}
        assert d["provenance"]["total"]["page"] == 1
        assert d["provenance"]["total"]["bbox"] == [0, 0, 1, 1]


class TestExtractionField:
    def test_to_dict_minimal(self):
        assert ExtractionField(value="x").to_dict() == {"value": "x"}

    def test_to_dict_full(self):
        f = ExtractionField(value="x", confidence=0.5, page=2, bbox=[1, 2, 3, 4],
                            source_text="raw")
        assert f.to_dict() == {
            "value": "x", "confidence": 0.5, "page": 2,
            "bbox": [1, 2, 3, 4], "source_text": "raw",
        }


class TestExtractionEngineABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ExtractionEngine()  # type: ignore[abstract]

    def test_default_capabilities(self):
        class Minimal(ExtractionEngine):
            @property
            def name(self):
                return "minimal"

            @property
            def supported_extensions(self):
                return {"pdf"}

            async def extract(self, file_path, schema, **kwargs):
                return ExtractionResult(data={}, engine_name=self.name)

            def is_available(self):
                return True

        caps = Minimal().capabilities
        assert caps == ExtractionCapabilities()
        assert caps.field_confidence is False
