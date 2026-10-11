import importlib

import pytest


def test_post_without_csrf_is_rejected(client, seeded_users, login_as):
    login_as(seeded_users["trekker"])

    response = client.post("/logout")

    assert response.status_code == 400


def test_post_with_session_csrf_reaches_route(client, seeded_users, login_as):
    token = login_as(seeded_users["trekker"])

    response = client.post("/logout", data={"csrf_token": token})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_secret_key_uses_environment(monkeypatch):
    import app as app_module

    monkeypatch.setenv("SECRET_KEY", "rotated-secret")
    reloaded = importlib.reload(app_module)

    assert reloaded.app.config["SECRET_KEY"] == "rotated-secret"

    monkeypatch.setenv("SECRET_KEY", "test-secret-from-environment")
    importlib.reload(app_module)


@pytest.mark.parametrize(
    ("role", "path", "fixture_name"),
    [
        ("trekker", "/logout", None),
        ("admin", "/admin/trek/delete/{id}", "trek"),
        ("admin", "/admin/user/toggle/{id}", "trekker_user"),
        ("admin", "/admin/user/approve/{id}", "staff_user"),
        ("trekker", "/user/book/{id}", "trek"),
        ("trekker", "/user/cancel/{id}", "booking"),
    ],
)
def test_state_changing_routes_do_not_accept_get(
    request, client, seeded_users, login_as, role, path, fixture_name
):
    login_as(seeded_users[role])
    target_id = None
    if fixture_name == "trek":
        target_id = request.getfixturevalue("trek").id
    elif fixture_name == "booking":
        target_id = request.getfixturevalue("booking").id
    elif fixture_name == "trekker_user":
        target_id = seeded_users["trekker"].id
    elif fixture_name == "staff_user":
        target_id = seeded_users["staff"].id

    response = client.get(path.format(id=target_id) if target_id else path)

    assert response.status_code == 405
