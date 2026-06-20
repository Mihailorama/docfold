"""Tests for extraction-quality metrics."""

from extractfold.evaluation.metrics import field_accuracy


class TestFieldAccuracy:
    def test_perfect_match(self):
        gold = {"name": "Acme", "total": 100}
        report = field_accuracy({"name": "Acme", "total": 100}, gold)
        assert report["accuracy"] == 1.0
        assert report["mismatched"] == []
        assert report["missing"] == []

    def test_partial_match(self):
        gold = {"name": "Acme", "total": 100}
        report = field_accuracy({"name": "Acme", "total": 200}, gold)
        assert report["accuracy"] == 0.5
        assert "total" in report["mismatched"]

    def test_missing_field(self):
        gold = {"name": "Acme", "total": 100}
        report = field_accuracy({"name": "Acme"}, gold)
        assert "total" in report["missing"]
        assert report["accuracy"] == 0.5

    def test_extra_field_does_not_lower_accuracy(self):
        gold = {"name": "Acme"}
        report = field_accuracy({"name": "Acme", "spurious": "x"}, gold)
        assert report["accuracy"] == 1.0
        assert "spurious" in report["extra"]

    def test_normalization(self):
        gold = {"total": "1000"}
        report = field_accuracy({"total": "1,000"}, gold, normalize=True)
        assert report["accuracy"] == 1.0

    def test_nested_and_list(self):
        gold = {"vendor": {"name": "Acme"}, "items": [{"sku": "A"}, {"sku": "B"}]}
        pred = {"vendor": {"name": "Acme"}, "items": [{"sku": "A"}, {"sku": "C"}]}
        report = field_accuracy(pred, gold)
        # 3 of 4 leaves match
        assert report["total_gold_fields"] == 3
        assert abs(report["accuracy"] - 2 / 3) < 1e-9
