import importlib


def _load_app_module():
    return importlib.import_module("app")


def test_signup_page_renders():
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()

    response = client.get("/signup")

    assert response.status_code == 200


def test_add_user_duplicate_email_redirects_to_login(monkeypatch, make_scripted_db):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    conn, _cursor = make_scripted_db(fetchone_values=[{"id": 1, "email": "a@b.com"}])
    monkeypatch.setattr(app_module, "get_db_connection", lambda: conn)
    monkeypatch.setattr(app_module.bcrypt, "hashpw", lambda pwd, _salt: b"hashed-" + pwd)

    client = app_module.app.test_client()
    response = client.post(
        "/add_user",
        data={
            "fname": "A",
            "lname": "B",
            "email": "a@b.com",
            "password": "secret",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_add_user_success_redirects_to_login(monkeypatch, make_scripted_db):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    conn, _cursor = make_scripted_db(fetchone_values=[None, {"id": 22}])
    monkeypatch.setattr(app_module, "get_db_connection", lambda: conn)
    monkeypatch.setattr(app_module.bcrypt, "hashpw", lambda pwd, _salt: b"hashed-" + pwd)

    client = app_module.app.test_client()
    response = client.post(
        "/add_user",
        data={
            "fname": "New",
            "lname": "User",
            "email": "new@site.com",
            "password": "secret",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert conn.committed is True


def test_login_validation_invalid_email(monkeypatch, make_scripted_db):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    conn, _cursor = make_scripted_db(fetchone_values=[None])
    monkeypatch.setattr(app_module, "get_db_connection", lambda: conn)

    client = app_module.app.test_client()
    response = client.post(
        "/login_validation",
        data={"email": "missing@test.com", "password": "x"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_validation_admin_success_sets_session(monkeypatch, make_scripted_db):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    conn, _cursor = make_scripted_db(
        fetchone_values=[
            {
                "id": 1,
                "first_name": "Admin",
                "email": "admin@test.com",
                "password": "stored",
                "role": "admin",
                "status": 1,
            }
        ]
    )
    monkeypatch.setattr(app_module, "get_db_connection", lambda: conn)
    monkeypatch.setattr(app_module.bcrypt, "checkpw", lambda *_args, **_kwargs: True)

    client = app_module.app.test_client()
    response = client.post(
        "/login_validation",
        data={"email": "admin@test.com", "password": "ok"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/dashboard")
    with client.session_transaction() as session:
        assert session.get("user_id") == 1
        assert session.get("role") == "admin"


def test_delete_poll_requires_auth(monkeypatch):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()

    response = client.post("/dashboard/poll/sample/delete")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_delete_poll_success(monkeypatch, make_scripted_db):
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    conn, _cursor = make_scripted_db(fetchone_values=[{"id": 33, "user_id": 9}])
    monkeypatch.setattr(app_module, "get_db_connection", lambda: conn)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 9

    response = client.post("/dashboard/poll/token-1/delete")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Poll deleted"
    assert conn.committed is True


def test_logout_clears_session():
    app_module = _load_app_module()
    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 4
        session["user_name"] = "Alex"
        session["role"] = "user"

    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "user_name" not in session
        assert "role" not in session
