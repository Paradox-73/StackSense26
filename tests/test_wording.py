"""Signs, articles and number formats in generated text."""
from engine.explain import _vs_text
from engine.export import _num
from engine.recommender import _article


def test_negative_margin_never_says_beats():
    s = _vs_text("React SPA", "Next.js", [], [], -1.8)
    assert "beats" not in s and "by -" not in s and "1.8" in s


def test_positive_margin_text():
    assert _vs_text("A", "B", [], [], 2.0).startswith("A beats B by 2.0")


def test_articles():
    assert _article("B2B / B2C SaaS") == "a"
    assert _article("E-commerce / marketplace") == "an"
    assert _article("ML / AI product") == "an"
    assert _article("IoT / telemetry ingestion") == "an"
    assert _article("Fintech / payments / ledger") == "a"
    assert _article("Internal tool / admin panel") == "an"


def test_small_numbers_do_not_print_as_zero():
    assert _num(0.3) == "0.3"
    assert _num(0.04) == "<0.1"
    assert _num(12345) == "12,345"
    assert _num(0) == "0"


def test_presets_text_has_no_bad_patterns(presets):
    import json
    import re

    from engine import recommend
    from engine.export import to_markdown

    bad = re.compile(r"by -\d|[−-]-\d|because your edited|\b[Aa]n '[BCDGJKPQTVWYZ]|\| [+-]0 \|")
    for pid, p in presets.items():
        r = recommend(p["input"], with_counterfactuals=True)
        txt = json.dumps(r, ensure_ascii=False) + to_markdown(r)
        assert not bad.search(txt), (pid, bad.search(txt).group(0))
