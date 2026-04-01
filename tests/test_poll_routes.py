from datetime import datetime, timedelta

from flask import Flask

from routes.poll_routes import poll_bp


def create_poll_app():
    app = Flask(__name__)
    app.secret_key = "poll-routes-test"

    @app.route("/login")
    def login():
        return "login"

    app.register_blueprint(poll_bp)
    return app


def test_create_poll_requires_question():
    app = create_poll_app()
    client = app.test_client()

    payload = {
        "question": "",
        "poll_type": "single",
        "start_time": (datetime.now() + timedelta(hours=2)).isoformat(timespec="minutes"),
        "end_time": (datetime.now() + timedelta(hours=3)).isoformat(timespec="minutes"),
        "options": [{"text": "A"}, {"text": "B"}],
    }
    response = client.post("/poll/create", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Poll question is required."


def test_create_poll_rejects_duplicate_options():
    app = create_poll_app()
    client = app.test_client()

    payload = {
        "question": "Q1",
        "poll_type": "single",
        "start_time": (datetime.now() + timedelta(hours=2)).isoformat(timespec="minutes"),
        "end_time": (datetime.now() + timedelta(hours=3)).isoformat(timespec="minutes"),
        "options": [{"text": "Same"}, {"text": "same"}],
    }
    response = client.post("/poll/create", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "All options must be unique."


def test_vote_page_redirects_to_login_if_not_authenticated():
    app = create_poll_app()
    client = app.test_client()

    response = client.get("/poll/some-token")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
