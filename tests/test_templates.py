import re

import pytest


def rendered(client, path):
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_shared_shell_loads_assets_without_inline_presentation(client):
    page = rendered(client, "/login")

    assert 'href="/static/css/app.css"' in page
    assert 'src="/static/js/app.js"' in page
    assert "<style" not in page.lower()
    assert re.search(r"\sstyle\s*=", page, re.IGNORECASE) is None
    assert re.search(r"\sonclick\s*=", page, re.IGNORECASE) is None
    assert 'href="#"' not in page


def test_shared_assets_expose_responsive_accessible_design_system(client):
    css = client.get("/static/css/app.css")
    script = client.get("/static/js/app.js")

    assert css.status_code == 200
    stylesheet = css.get_data(as_text=True)
    assert "--color-primary" in stylesheet
    assert ":focus-visible" in stylesheet
    assert "prefers-reduced-motion" in stylesheet
    assert "max-width: 420px" in stylesheet
    assert script.status_code == 200
    assert "data-confirm" in script.get_data(as_text=True)


def test_authenticated_shell_links_brand_home_and_marks_current_page(
    client, seeded_users, login_as
):
    login_as(seeded_users["admin"])

    page = rendered(client, "/admin/dashboard")

    assert re.search(r'<a[^>]+class="[^"]*brand[^"]*"[^>]+href="/admin/dashboard"', page)
    assert re.search(r'href="/admin/dashboard"[^>]+aria-current="page"', page)
    assert '<form method="POST" action="/logout"' in page
    assert 'name="csrf_token"' in page


def test_flash_messages_use_accessible_live_region(client):
    response = client.get("/admin/dashboard", follow_redirects=True)
    page = response.get_data(as_text=True)

    assert 'aria-live="polite"' in page
    assert "Please login first" in page


def test_login_uses_public_brand_and_form_panels_with_complete_labels(client):
    page = rendered(client, "/login")

    assert 'class="public-shell"' in page
    assert 'class="brand-panel"' in page
    assert 'class="form-panel"' in page
    assert 'for="login-email"' in page
    assert 'for="login-password"' in page
    assert 'name="csrf_token"' in page


def test_registration_uses_public_brand_and_form_panels_with_complete_labels(client):
    page = rendered(client, "/register")

    assert 'class="public-shell"' in page
    assert 'class="brand-panel"' in page
    assert 'class="form-panel"' in page
    for control_id in (
        "register-name",
        "register-email",
        "register-password",
        "register-role",
    ):
        assert f'for="{control_id}"' in page
    assert 'name="csrf_token"' in page


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/dashboard"),
        ("admin", "/admin/treks"),
        ("admin", "/admin/trek/create"),
        ("admin", "/admin/users"),
        ("admin", "/admin/bookings"),
        ("admin", "/admin/charts"),
        ("staff", "/staff/dashboard"),
        ("staff", "/staff/profile"),
        ("staff", "/staff/charts"),
        ("trekker", "/user/dashboard"),
        ("trekker", "/user/treks"),
        ("trekker", "/user/bookings"),
        ("trekker", "/user/profile"),
        ("trekker", "/user/history"),
        ("trekker", "/user/charts"),
    ],
)
def test_role_pages_use_consistent_clean_page_header(
    client, seeded_users, login_as, role, path
):
    login_as(seeded_users[role])

    page = rendered(client, path)

    assert '<header class="page-header"' in page
    assert re.search(r'<h1(?:\s[^>]*)?>[^<]+</h1>', page)
    assert re.search(r"\sstyle\s*=", page, re.IGNORECASE) is None
    assert re.search(r"\sonclick\s*=", page, re.IGNORECASE) is None
    assert not any(marker in page for marker in ("â", "ð", "�"))
    assert re.search(r"[\u2600-\u27bf\U0001f300-\U0001faff]", page) is None


def test_detail_and_edit_pages_follow_page_contract(
    client, seeded_users, login_as, trek
):
    for role, path in (
        ("admin", f"/admin/trek/edit/{trek.id}"),
        ("staff", f"/staff/trek/{trek.id}"),
    ):
        login_as(seeded_users[role])
        page = rendered(client, path)
        assert '<header class="page-header"' in page
        assert re.search(r'<h1(?:\s[^>]*)?>[^<]+</h1>', page)
        assert re.search(r"\sstyle\s*=", page, re.IGNORECASE) is None
        assert re.search(r"\sonclick\s*=", page, re.IGNORECASE) is None


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/treks"),
        ("admin", "/admin/users"),
        ("admin", "/admin/bookings"),
        ("staff", "/staff/dashboard"),
        ("trekker", "/user/treks"),
        ("trekker", "/user/bookings"),
        ("trekker", "/user/history"),
    ],
)
def test_collection_pages_provide_responsive_collection_region(
    client, seeded_users, login_as, role, path
):
    login_as(seeded_users[role])

    page = rendered(client, path)

    assert 'class="collection-region' in page


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/treks"),
        ("admin", "/admin/bookings"),
        ("staff", "/staff/dashboard"),
        ("staff", "/staff/charts"),
        ("trekker", "/user/treks"),
        ("trekker", "/user/bookings"),
        ("trekker", "/user/history"),
        ("trekker", "/user/charts"),
    ],
)
def test_empty_collections_offer_useful_empty_state(
    client, seeded_users, login_as, role, path
):
    login_as(seeded_users[role])

    page = rendered(client, path)

    assert 'class="empty-state"' in page
