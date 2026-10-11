import pytest
from werkzeug.security import check_password_hash

from models import User, db


def csrf_post(client, path, token, data=None, **kwargs):
    payload = dict(data or {})
    payload["csrf_token"] = token
    return client.post(path, data=payload, **kwargs)


def test_login_normalizes_mixed_case_email(client, seeded_users, login_as):
    token = login_as(seeded_users["trekker"])
    client.post("/logout", data={"csrf_token": token})
    client.get("/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(
        client,
        "/login",
        token,
        {"email": "  TREKKER@Example.COM ", "password": "password123"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/user/dashboard")


@pytest.mark.parametrize(
    ("data", "expected_message"),
    [
        ({"name": "   ", "email": "new@example.com", "password": "password123", "role": "trekker"}, "name"),
        ({"name": "New User", "email": "not-an-email", "password": "password123", "role": "trekker"}, "email"),
        ({"name": "New User", "email": "new@example.com", "password": "short", "role": "trekker"}, "8"),
        ({"name": "New User", "email": "new@example.com", "password": "password123", "role": "admin"}, "role"),
    ],
)
def test_registration_rejects_invalid_input(
    client, app_context, data, expected_message
):
    client.get("/register")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(client, "/register", token, data, follow_redirects=True)

    assert response.status_code == 200
    assert expected_message.lower() in response.get_data(as_text=True).lower()
    assert User.query.filter_by(email=data["email"].strip().lower()).first() is None


def test_registration_rejects_duplicate_email_case_insensitively(
    client, seeded_users
):
    client.get("/register")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(
        client,
        "/register",
        token,
        {
            "name": "Another Trekker",
            "email": "TREKKER@example.com",
            "password": "password123",
            "role": "trekker",
        },
        follow_redirects=True,
    )

    assert "already exists" in response.get_data(as_text=True).lower()
    assert User.query.filter(db.func.lower(User.email) == "trekker@example.com").count() == 1


def test_registration_preserves_non_secret_input_after_validation_error(
    client, app_context
):
    client.get("/register")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(
        client,
        "/register",
        token,
        {
            "name": "Nila Walker",
            "email": "nila@example.com",
            "password": "short",
            "role": "staff",
        },
        follow_redirects=True,
    )

    page = response.get_data(as_text=True)
    assert 'value="Nila Walker"' in page
    assert 'value="nila@example.com"' in page
    assert 'value="staff" selected' in page
    assert "short" not in page


def test_valid_registration_normalizes_email(client, app_context):
    client.get("/register")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(
        client,
        "/register",
        token,
        {
            "name": "  Nila Walker  ",
            "email": "  NILA@Example.COM ",
            "password": "password123",
            "role": "trekker",
        },
    )

    created = User.query.filter_by(email="nila@example.com").one()
    assert response.status_code == 302
    assert created.name == "Nila Walker"
    assert created.is_approved is True


@pytest.mark.parametrize(
    ("account_change", "message"),
    [("inactive", "deactivated"), ("pending", "pending")],
)
def test_login_rejects_unavailable_accounts(
    client, seeded_users, account_change, message
):
    user = seeded_users["staff"]
    if account_change == "inactive":
        user.is_active = False
    else:
        user.is_approved = False
    db.session.commit()
    client.get("/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]

    response = csrf_post(
        client,
        "/login",
        token,
        {"email": user.email, "password": "password123"},
        follow_redirects=True,
    )

    assert message in response.get_data(as_text=True).lower()
    with client.session_transaction() as session:
        assert "user_id" not in session


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/dashboard"),
        ("staff", "/staff/dashboard"),
        ("trekker", "/user/dashboard"),
    ],
)
def test_each_role_can_open_its_dashboard(
    client, seeded_users, login_as, role, path
):
    login_as(seeded_users[role])

    response = client.get(path)

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("role", "wrong_path", "own_path"),
    [
        ("admin", "/staff/dashboard", "/admin/dashboard"),
        ("staff", "/user/dashboard", "/staff/dashboard"),
        ("trekker", "/admin/dashboard", "/user/dashboard"),
    ],
)
def test_wrong_role_redirects_to_own_dashboard(
    client, seeded_users, login_as, role, wrong_path, own_path
):
    login_as(seeded_users[role])

    response = client.get(wrong_path)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(own_path)


def test_profile_rejects_whitespace_name_and_preserves_password(
    client, seeded_users, login_as
):
    user = seeded_users["trekker"]
    original_password = user.password
    token = login_as(user)

    response = csrf_post(
        client,
        "/user/profile",
        token,
        {"name": "   ", "password": "new-password"},
        follow_redirects=True,
    )

    db.session.refresh(user)
    assert "name" in response.get_data(as_text=True).lower()
    assert user.name == "Tara Trekker"
    assert user.password == original_password


def test_profile_accepts_valid_name_and_password(client, seeded_users, login_as):
    user = seeded_users["staff"]
    token = login_as(user)

    response = csrf_post(
        client,
        "/staff/profile",
        token,
        {"name": "  Samira Guide ", "password": "new-password"},
    )

    db.session.refresh(user)
    assert response.status_code == 302
    assert user.name == "Samira Guide"
    assert check_password_hash(user.password, "new-password")


def test_logout_requires_post_and_clears_session(client, seeded_users, login_as):
    token = login_as(seeded_users["trekker"])

    response = csrf_post(client, "/logout", token)

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "user_id" not in session
