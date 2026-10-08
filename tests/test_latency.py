from backend.latency import rtf, summarize


def test_rtf():
    assert rtf(5.0, 10.0) == 0.5


def test_summarize():
    s = summarize([100.0, 200.0, 300.0])
    assert s["n"] == 3
    assert s["mean"] == 200.0
    assert s["median"] == 200.0
    assert s["min"] == 100.0
    assert s["max"] == 300.0


def test_summarize_empty():
    assert summarize([]) == {}
