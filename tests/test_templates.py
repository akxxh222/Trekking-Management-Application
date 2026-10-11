import re


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
