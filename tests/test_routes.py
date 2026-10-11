from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound

from app import app


class InteractionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.forms = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        elif tag == "form":
            self._form = {
                "action": attributes.get("action", ""),
                "method": attributes.get("method", "GET").upper(),
                "has_csrf": False,
            }
        elif tag == "input" and self._form is not None:
            if attributes.get("name") == "csrf_token" and attributes.get("value"):
                self._form["has_csrf"] = True

    def handle_endtag(self, tag):
        if tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None


def test_sensitive_state_changes_are_post_only():
    expected = {
        "logout": {"POST", "OPTIONS"},
        "delete_trek": {"POST", "OPTIONS"},
        "assign_staff": {"POST", "OPTIONS"},
        "toggle_user": {"POST", "OPTIONS"},
        "approve_staff": {"POST", "OPTIONS"},
        "update_booking_status": {"POST", "OPTIONS"},
        "staff_update_trek": {"POST", "OPTIONS"},
        "book_trek": {"POST", "OPTIONS"},
        "cancel_booking": {"POST", "OPTIONS"},
    }
    methods = {rule.endpoint: rule.methods for rule in app.url_map.iter_rules()}

    for endpoint, allowed in expected.items():
        assert methods[endpoint] == allowed


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/dashboard"),
        ("admin", "/admin/treks"),
        ("admin", "/admin/trek/create"),
        ("admin", "/admin/trek/edit/{trek_id}"),
        ("admin", "/admin/users"),
        ("admin", "/admin/bookings"),
        ("admin", "/admin/charts"),
        ("staff", "/staff/dashboard"),
        ("staff", "/staff/trek/{trek_id}"),
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
def test_rendered_controls_resolve_and_post_forms_have_csrf(
    client, seeded_users, login_as, trek, booking, role, path
):
    login_as(seeded_users[role])
    request_path = path.format(trek_id=trek.id)
    response = client.get(request_path)
    assert response.status_code == 200
    parser = InteractionParser()
    parser.feed(response.get_data(as_text=True))
    adapter = app.url_map.bind("localhost")

    for target in parser.links:
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith("#"):
            continue
        try:
            adapter.match(parsed.path, method="GET")
        except (NotFound, MethodNotAllowed) as error:
            pytest.fail(f"Broken GET link {target!r} on {path}: {error}")

    for form in parser.forms:
        parsed = urlsplit(form["action"] or request_path)
        try:
            adapter.match(parsed.path, method=form["method"])
        except (NotFound, MethodNotAllowed) as error:
            pytest.fail(f"Broken {form['method']} form {form['action']!r} on {path}: {error}")
        if form["method"] == "POST":
            assert form["has_csrf"], f"POST form {form['action']!r} on {path} lacks CSRF"


def test_public_forms_resolve_and_include_csrf(client):
    adapter = app.url_map.bind("localhost")
    for path in ("/login", "/register"):
        response = client.get(path)
        parser = InteractionParser()
        parser.feed(response.get_data(as_text=True))
        for form in parser.forms:
            adapter.match(urlsplit(form["action"]).path, method=form["method"])
            assert form["method"] != "POST" or form["has_csrf"]


def test_repository_templates_have_no_inert_or_inline_controls():
    template_root = Path(__file__).resolve().parents[1] / "templates"
    forbidden = ('href="#"', "onclick=", "style=", "â", "ð", "�")

    for template in template_root.rglob("*.html"):
        contents = template.read_text(encoding="utf-8").lower()
        for marker in forbidden:
            assert marker not in contents, f"{template.relative_to(template_root)} contains {marker!r}"
