import os
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-from-environment"

from app import app as flask_app  # noqa: E402
from models import Booking, Trek, User, db  # noqa: E402


@pytest.fixture()
def app_context():
    flask_app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app_context):
    return app_context.test_client()


@pytest.fixture()
def seeded_users(app_context):
    users = {
        "admin": User(
            name="Asha Admin",
            email="admin@example.com",
            password=generate_password_hash("password123"),
            role="admin",
            is_active=True,
            is_approved=True,
        ),
        "staff": User(
            name="Sam Guide",
            email="staff@example.com",
            password=generate_password_hash("password123"),
            role="staff",
            is_active=True,
            is_approved=True,
        ),
        "trekker": User(
            name="Tara Trekker",
            email="trekker@example.com",
            password=generate_password_hash("password123"),
            role="trekker",
            is_active=True,
            is_approved=True,
        ),
    }
    db.session.add_all(users.values())
    db.session.commit()
    return users


@pytest.fixture()
def login_as(client):
    def login(user, csrf_token="known-csrf-token"):
        with client.session_transaction() as session:
            session["user_id"] = user.id
            session["role"] = user.role
            session["name"] = user.name
            session["csrf_token"] = csrf_token
        return csrf_token

    return login


@pytest.fixture()
def trek(app_context, seeded_users):
    item = Trek(
        name="Munnar Ridge",
        location="Kerala",
        difficulty="Medium",
        duration_days=3,
        total_slots=12,
        available_slots=12,
        status="Open",
        assigned_staff_id=seeded_users["staff"].id,
    )
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture()
def booking(app_context, seeded_users, trek):
    item = Booking(
        user_id=seeded_users["trekker"].id,
        trek_id=trek.id,
        booking_date="2026-10-11",
        status="Booked",
        payment_status="Paid",
    )
    trek.available_slots -= 1
    db.session.add(item)
    db.session.commit()
    return item
