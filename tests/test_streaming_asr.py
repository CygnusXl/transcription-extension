from backend.streaming_asr import LocalAgreement, StreamingASR, Word, join_words

from .fakes import SCRIPT, SCRIPT_TEXT, make_fake_transcriber, pcm_silence


def run(asr, seconds, step=1.0):
    """Feed audio second by second and collect the result of every step."""
    results = []
    for _ in range(int(seconds / step)):
        asr.feed(pcm_silence(step))
        assert asr.ready()
        results.append(asr.step())
    return results


def test_words_commit_only_after_two_agreeing_hypotheses():
    asr = StreamingASR(make_fake_transcriber(), step_seconds=1.0)
    results = run(asr, 7)

    # Step 1: nothing is stable yet, but a partial is already visible.
    assert results[0].committed == []
    assert results[0].tentative

    committed = [w for r in results for w in r.committed]
    assert join_words(committed) == SCRIPT_TEXT
    assert "wrongword" not in join_words(committed)  # unstable tail never committed
    # Commits arrive progressively, not all at once.
    assert sum(1 for r in results if r.committed) >= 4


def test_tentative_text_is_visible_before_it_is_committed():
    asr = StreamingASR(make_fake_transcriber(), step_seconds=1.0)
    results = run(asr, 3)
    assert any("wrongword" in join_words(r.tentative) for r in results)


def test_buffer_is_trimmed_and_no_words_are_lost_or_duplicated():
    long_script = [(f" w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(40)]  # 20 s of speech
    asr = StreamingASR(make_fake_transcriber(long_script), step_seconds=1.0, max_buffer_seconds=4.0)
    results = run(asr, 22)  # 2 s of trailing silence so the last word is no longer "unstable"
    fin = asr.finish()
    committed = [w for r in results for w in r.committed] + fin.committed
    assert [w.text for w in committed] == [t for t, _, _ in long_script]
    assert asr.buffer_start > 10.0  # the window moved forward instead of growing without bound


def test_finish_commits_remaining_tentative_words():
    asr = StreamingASR(make_fake_transcriber(), step_seconds=1.0)
    results = run(asr, 5)
    committed = [w for r in results for w in r.committed]
    assert join_words(committed) != SCRIPT_TEXT  # the last word is still only tentative
    fin = asr.finish()
    assert fin.committed
    assert join_words(committed + fin.committed) == SCRIPT_TEXT
    assert fin.tentative == []


def test_silence_does_not_grow_the_buffer():
    asr = StreamingASR(make_fake_transcriber(script=[]), step_seconds=1.0)
    run(asr, 30)
    assert asr.fed_seconds - asr.buffer_start <= 6.0


def test_language_locks_after_confident_speech_and_manual_choice_wins():
    calls = []
    asr = StreamingASR(make_fake_transcriber(calls=calls), step_seconds=1.0)
    run(asr, 6)
    assert asr.locked_language == "en"
    assert calls[0][2] is None and calls[-1][2] == "en"  # detection only until locked

    manual_calls = []
    asr2 = StreamingASR(make_fake_transcriber(calls=manual_calls), step_seconds=1.0, language="ja")
    run(asr2, 3)
    assert {c[2] for c in manual_calls} == {"ja"}


def test_reset_discards_buffer_but_keeps_the_audio_clock():
    asr = StreamingASR(make_fake_transcriber(), step_seconds=1.0)
    run(asr, 3)
    asr.reset()
    assert asr.buffer_start == asr.fed_seconds == 3.0
    assert asr.agreement.prev == [] and asr.agreement.committed_end == 3.0


def test_local_agreement_removes_overlap_with_committed_tail():
    la = LocalAgreement()
    la.commit([Word(0.0, 0.5, "hello"), Word(0.5, 1.0, " world")])
    hyp = [Word(0.05, 0.52, "hello"), Word(0.52, 1.0, " world"), Word(1.0, 1.5, " again")]
    assert [w.text for w in la.update(hyp)[1]] == [" again"]
