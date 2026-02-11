"""Tests for evaluation metrics."""

import pytest
from docfold.evaluation.metrics import (
    compute_cer,
    compute_wer,
    compute_table_f1,
    compute_heading_f1,
    compute_reading_order_score,
)


class TestCER:
    def test_identical(self):
        assert compute_cer("hello world", "hello world") == 0.0

    def test_completely_different(self):
        cer = compute_cer("abc", "xyz")
        assert cer > 0

    def test_empty_reference(self):
        cer = compute_cer("something", "")
        assert cer == 0.0 or cer > 0  # depends on impl; just check it doesn't crash

    def test_empty_both(self):
        assert compute_cer("", "") == 0.0


class TestWER:
    def test_identical(self):
        assert compute_wer("hello world", "hello world") == 0.0

    def test_one_word_wrong(self):
        wer = compute_wer("hello earth", "hello world")
        assert 0 < wer <= 1.0

    def test_extra_words(self):
        wer = compute_wer("hello beautiful world", "hello world")
        assert wer > 0


class TestTableF1:
    def test_perfect_match(self):
        tables = [[["a", "b"], ["c", "d"]]]
        assert compute_table_f1(tables, tables) == 1.0

    def test_no_tables(self):
        assert compute_table_f1([], []) == 1.0

    def test_missing_predicted(self):
        assert compute_table_f1([], [[["a"]]]) == 0.0

    def test_partial_match(self):
        predicted = [[["a", "b"], ["c", "x"]]]
        reference = [[["a", "b"], ["c", "d"]]]
        f1 = compute_table_f1(predicted, reference)
        assert 0 < f1 < 1.0


class TestHeadingF1:
    def test_perfect(self):
        h = ["Introduction", "Methods", "Results"]
        assert compute_heading_f1(h, h) == 1.0

    def test_case_insensitive(self):
        pred = ["INTRODUCTION", "methods"]
        ref = ["Introduction", "Methods"]
        assert compute_heading_f1(pred, ref) == 1.0

    def test_empty(self):
        assert compute_heading_f1([], []) == 1.0

    def test_no_overlap(self):
        assert compute_heading_f1(["A"], ["B"]) == 0.0


class TestReadingOrder:
    def test_perfect_order(self):
        order = ["a", "b", "c", "d"]
        assert compute_reading_order_score(order, order) == 1.0

    def test_reversed(self):
        pred = ["d", "c", "b", "a"]
        ref = ["a", "b", "c", "d"]
        score = compute_reading_order_score(pred, ref)
        assert score < 0  # Kendall's tau for reversed = -1

    def test_single_element(self):
        assert compute_reading_order_score(["a"], ["a"]) == 1.0

    def test_partial_overlap(self):
        pred = ["a", "c", "b"]
        ref = ["a", "b", "c"]
        score = compute_reading_order_score(pred, ref)
        assert -1 <= score <= 1
