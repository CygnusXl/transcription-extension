from backend import database


def test_segments_and_translations_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "c.sqlite3")
    database.init_db()
    database.set_status("vid", "live", "en")
    database.save_segment("vid", 1000, 2500, "en", "Hello there.")
    database.save_segment("vid", 1000, 2600, "en", "Hello there.")  # upsert, not duplicate
    database.save_translation("vid", 1000, "id", "Halo.")

    rows = database.load_segments("vid", "id")
    assert rows == [
        {"start_ms": 1000, "end_ms": 2600, "source_lang": "en", "text": "Hello there.", "translation": "Halo."}
    ]
    assert database.load_segments("vid", "de")[0]["translation"] is None
