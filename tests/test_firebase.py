from utils import firebase


class FakeRef:
    def __init__(self):
        self.payload = None

    def set(self, payload):
        self.payload = payload


def test_push_poll_results_writes_expected_payload(monkeypatch):
    fake_ref = FakeRef()

    monkeypatch.setattr(firebase, "init_firebase", lambda: None)
    monkeypatch.setattr(firebase.db, "reference", lambda path: fake_ref)

    firebase.push_poll_results(
        poll_id=7,
        results=[{"option": "A", "votes": 3, "percentage": 60.0}],
        total_votes=5,
    )

    assert fake_ref.payload["poll_id"] == 7
    assert fake_ref.payload["total_votes"] == 5
    assert fake_ref.payload["results"][0]["option"] == "A"
    assert fake_ref.payload["updated_at"] == {".sv": "timestamp"}


def test_push_poll_results_does_not_raise_on_error(monkeypatch):
    monkeypatch.setattr(firebase, "init_firebase", lambda: None)

    def blow_up(_path):
        raise RuntimeError("firebase unavailable")

    monkeypatch.setattr(firebase.db, "reference", blow_up)

    # should not raise
    firebase.push_poll_results(
        poll_id=1,
        results=[],
        total_votes=0,
    )
