"""Tests for AdaptiveThreshold."""

from modelhop.core.adaptive_threshold import AdaptiveThreshold


def test_adjust_tightens_when_quality_low(tmp_path):
    at = AdaptiveThreshold(initial=0.7, data_dir=str(tmp_path))
    at.adjust(0.6)
    at.adjust(0.5)
    at.adjust(0.55)
    at.adjust(0.65)
    at.adjust(0.6)
    at.adjust(0.55)
    at.adjust(0.6)
    at.adjust(0.5)
    at.adjust(0.55)
    at.adjust(0.55)  # 10 outcomes, avg < 0.7 -> threshold up
    assert at.get_threshold() > 0.7


def test_adjust_relaxes_when_quality_high(tmp_path):
    at = AdaptiveThreshold(initial=0.7, data_dir=str(tmp_path))
    for _ in range(10):
        at.adjust(0.9)  # 10 outcomes, avg > 0.85 -> threshold down
    assert at.get_threshold() < 0.7


def test_clamp_min_max(tmp_path):
    at = AdaptiveThreshold(initial=0.5, data_dir=str(tmp_path))
    at.threshold = 0.5  # at min
    for _ in range(10):
        at.adjust(0.5)
    assert at.get_threshold() >= 0.5

    at2 = AdaptiveThreshold(initial=0.9, data_dir=str(tmp_path))
    at2.threshold = 0.9  # at max
    for _ in range(10):
        at2.adjust(0.95)
    assert at2.get_threshold() <= 0.9


def test_persist_and_load(tmp_path):
    at = AdaptiveThreshold(initial=0.7, data_dir=str(tmp_path))
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)
    at.adjust(0.9)  # 10 outcomes -> threshold lowered
    new_threshold = at.get_threshold()

    at2 = AdaptiveThreshold(initial=0.7, data_dir=str(tmp_path))
    assert at2.get_threshold() == new_threshold
