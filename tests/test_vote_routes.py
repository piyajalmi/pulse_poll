from datetime import datetime, timezone, timedelta

from flask import Flask

from routes.vote_routes import vote_bp


class FakeCursor:
    def __init__(self, fetchone_values, fetchall_values):
        self.fetchone_values = list(fetchone_values)
        self.fetchall_values = list(fetchall_values)
        self.closed = False

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def fetchall(self):
        if not self.fetchall_values:
            return []
        return self.fetchall_values.pop(0)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def create_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(vote_bp)
    return app


def test_get_results_success(monkeypatch):
    poll = {
        "id": 10,
        "question": "Best language?",
        "end_time": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    options = [
        {"id": 1, "option": "Python"},
        {"id": 2, "option": "JavaScript"},
    ]
    all_votes = [
        {"selected_option_id": 1, "count": 3},
        {"selected_option_id": 2, "count": 2},
    ]

    fake_cursor = FakeCursor(
        fetchone_values=[poll, {"total": 5}],
        fetchall_values=[options, all_votes],
    )
    fake_conn = FakeConnection(fake_cursor)

    from routes import vote_routes

    monkeypatch.setattr(vote_routes, "get_db_connection", lambda: fake_conn)
    pushed = {}

    def fake_push(poll_id, results, total_votes):
        pushed["poll_id"] = poll_id
        pushed["results"] = results
        pushed["total_votes"] = total_votes

    monkeypatch.setattr(vote_routes, "push_poll_results", fake_push)

    app = create_test_app()
    client = app.test_client()

    response = client.get("/api/poll/sample-token/results")
    data = response.get_json()

    assert response.status_code == 200
    assert data["poll_id"] == 10
    assert data["question"] == "Best language?"
    assert data["total_votes"] == 5
    assert data["results"][0]["option"] == "Python"
    assert data["results"][0]["votes"] == 3
    assert data["results"][0]["percentage"] == 60.0

    assert pushed["poll_id"] == 10
    assert pushed["total_votes"] == 5
    assert fake_cursor.closed is True
    assert fake_conn.closed is True


def test_get_results_poll_not_found(monkeypatch):
    fake_cursor = FakeCursor(fetchone_values=[None], fetchall_values=[])
    fake_conn = FakeConnection(fake_cursor)

    from routes import vote_routes

    monkeypatch.setattr(vote_routes, "get_db_connection", lambda: fake_conn)

    pushed = {"called": False}

    def fake_push(*_args, **_kwargs):
        pushed["called"] = True

    monkeypatch.setattr(vote_routes, "push_poll_results", fake_push)

    app = create_test_app()
    client = app.test_client()

    response = client.get("/api/poll/missing-token/results")
    data = response.get_json()

    assert response.status_code == 404
    assert data["error"] == "Poll not found."
    assert pushed["called"] is False
    assert fake_cursor.closed is True
    assert fake_conn.closed is True
