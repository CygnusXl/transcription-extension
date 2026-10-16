from backend.streaming_asr import Word
from backend.transcript import LineBuilder


def W(text, s, e):
    return Word(s, e, text)


def test_partial_line_keeps_its_id_until_closed_by_sentence_end():
    lb = LineBuilder()
    u = lb.update([], [W("Hello", 0, 0.4)])
    assert [(x.id, x.text, x.final) for x in u] == [(0, "Hello", False)]

    u = lb.update([W("Hello", 0, 0.4)], [W(" there", 0.4, 0.8)])
    assert [(x.id, x.text, x.final) for x in u] == [(0, "Hello there", False)]

    u = lb.update([W(" there.", 0.4, 0.9)], [W(" Next", 1.0, 1.3)])
    assert [(x.id, x.text, x.final) for x in u] == [(0, "Hello there.", True), (1, "Next", False)]


def test_long_line_is_split_by_length():
    lb = LineBuilder(max_chars=20)
    words = [W(f" word{i}", i, i + 0.5) for i in range(6)]
    out = lb.update(words, [])
    finals = [x for x in out if x.final]
    assert finals and all(len(x.text) >= 20 for x in finals)


def test_stale_partial_is_retracted_with_empty_text():
    lb = LineBuilder()
    lb.update([], [W("Hmm", 0, 0.3)])
    u = lb.update([], [])
    assert [(x.id, x.text, x.final) for x in u] == [(0, "", False)]
    assert lb.update([], []) == []  # only retracted once


def test_finish_closes_the_open_line_without_leaving_a_partial():
    lb = LineBuilder()
    lb.update([W("Almost", 0, 0.5)], [W(" done", 0.5, 0.9)])
    out = lb.finish([W("Almost", 0, 0.5), W(" done", 0.5, 0.9)])
    # `Almost` was already committed earlier in this test only via update(); finish adds both again,
    # so check the invariant that matters: exactly one final, nothing partial.
    assert [x.final for x in out] == [True]
