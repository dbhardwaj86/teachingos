from samagra.pratham import identity, service, store


def test_mark_done_writes_a_done_row():
    assert service.mark_done("stu_a", "circular-motion", "revision") is True
    rows = store.list_progress("stu_a")
    assert len(rows) == 1 and rows[0]["status"] == "done"
    assert rows[0]["marked_at"]          # stamped via identity.now_iso()


def test_mark_done_rate_limited_returns_false_and_does_not_write(monkeypatch):
    monkeypatch.setattr(service, "_PROGRESS_LIMITER",
                        identity.RateLimiter(max_attempts=1, window_seconds=60))
    assert service.mark_done("stu_a", "c1", "revision", now_epoch=1000.0) is True
    assert service.mark_done("stu_a", "c2", "revision", now_epoch=1001.0) is False
    assert len(store.list_progress("stu_a")) == 1     # the refused mark never wrote


def test_progress_for_delegates_to_store():
    service.mark_done("stu_a", "gravitation", "deck")
    assert service.progress_for("stu_a")[0]["chapter"] == "gravitation"
    assert service.progress_for("stu_b") == []
