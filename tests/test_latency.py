from backend.latency import SAMPLE_RATE, ArrivalClock, rtf, summarize


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


def test_arrival_clock_interpolates_within_a_chunk():
    clock = ArrivalClock()
    # 100 ms chunks arriving at t = 10.1, 10.2, 10.3 (wall clock)
    for i in range(1, 4):
        clock.record(i * SAMPLE_RATE // 10, wall_time=10.0 + i * 0.1)
    # The end of the 2nd chunk (0.2 s of audio) was captured when it arrived.
    assert abs(clock.capture_time(0.2) - 10.2) < 1e-6
    # 0.15 s is halfway through the 2nd chunk -> 50 ms before its arrival.
    assert abs(clock.capture_time(0.15) - 10.15) < 1e-6


def test_arrival_clock_empty():
    assert ArrivalClock().capture_time(1.0) is None
