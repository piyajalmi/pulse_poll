from datetime import datetime, timezone, timedelta

from flask import Flask

from routes.vote_routes import vote_bp


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.closed = False

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_values.pop(0) if self.fetchall_values else []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def create_vote_app():
    app = Flask(__name__)
    app.secret_key = "vote-submit-test"
    app.register_blueprint(vote_bp)
    return app


def test_submit_vote_poll_not_found(monkeypatch):
    from routes import vote_routes

    cursor = FakeCursor(fetchone_values=[None])
    conn = FakeConnection(cursor)
    monkeypatch.setattr(vote_routes, "get_db_connection", lambda: conn)

    app = create_vote_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 4

    response = client.post("/poll/missing/vote", json={"option_ids": [1]})

    assert response.status_code == 404
    assert response.get_json()["error"] == "Poll not found."


def test_submit_vote_rejects_empty_option_selection(monkeypatch):
    from routes import vote_routes

    poll = {
        "id": 1,
        "poll_type": "single",
        "start_time": datetime.now(timezone.utc) - timedelta(hours=1),
        "end_time": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    cursor = FakeCursor(fetchone_values=[poll, None])
    conn = FakeConnection(cursor)
    monkeypatch.setattr(vote_routes, "get_db_connection", lambda: conn)

    app = create_vote_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 4

    response = client.post("/poll/token-1/vote", json={"option_ids": []})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No option selected."


def test_submit_vote_success_pushes_realtime_updates(monkeypatch):
    from routes import vote_routes

    poll = {
        "id": 9,
        "poll_type": "single",
        "start_time": datetime.now(timezone.utc) - timedelta(hours=1),
        "end_time": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    options = [{"id": 1, "option": "Option A"}]
    votes = [{"selected_option_id": 1, "count": 1}]

    # fetchone order:
    # 1) poll lookup
    # 2) duplicate vote check
    # 3) option validity
    # 4) inserted vote id
    # 5) total votes row
    cursor = FakeCursor(
        fetchone_values=[poll, None, {"id": 1}, {"id": 101}, {"total": 1}],
        fetchall_values=[options, votes],
    )
    conn = FakeConnection(cursor)

    monkeypatch.setattr(vote_routes, "get_db_connection", lambda: conn)
    monkeypatch.setattr(vote_routes, "hash_ip", lambda _ip: "hashed")
    monkeypatch.setattr(vote_routes, "encrypt_identifier", lambda value: f"enc-{value}")

    pushed = {"called": False}

    def fake_push(poll_id, results, total_votes):
        pushed["called"] = True
        pushed["poll_id"] = poll_id
        pushed["total_votes"] = total_votes
        pushed["result_option"] = results[0]["option"]

    monkeypatch.setattr(vote_routes, "push_poll_results", fake_push)

    app = create_vote_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7

    response = client.post(
        "/poll/token-ok/vote",
        json={"option_ids": [1], "submission_id": "sub-1"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["message"] == "Vote submitted successfully!"
    assert body["results_link"] == "/poll/token-ok/results"
    assert conn.committed is True
    assert pushed["called"] is True
    assert pushed["poll_id"] == 9
    assert pushed["total_votes"] == 1
    assert pushed["result_option"] == "Option A"
