import pytest

from models import Trek, User, db


def admin_post(client, login_as, admin, path, data=None, follow_redirects=False):
    token = login_as(admin)
    payload = dict(data or {})
    payload["csrf_token"] = token
    return client.post(path, data=payload, follow_redirects=follow_redirects)


def valid_trek_data(**changes):
    data = {
        "name": "Nilgiri Traverse",
        "location": "Tamil Nadu",
        "difficulty": "Medium",
        "duration_days": "4",
        "total_slots": "14",
        "status": "Open",
    }
    data.update(changes)
    return data


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"name": "   "}, "name"),
        ({"location": ""}, "location"),
        ({"difficulty": "Extreme"}, "difficulty"),
        ({"duration_days": "many"}, "duration"),
        ({"duration_days": "0"}, "duration"),
        ({"duration_days": "-2"}, "duration"),
        ({"total_slots": "many"}, "slots"),
        ({"total_slots": "0"}, "slots"),
        ({"total_slots": "-1"}, "slots"),
    ],
)
def test_create_trek_rejects_invalid_input(
    client, seeded_users, login_as, changes, message
):
    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        "/admin/trek/create",
        valid_trek_data(**changes),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert message in response.get_data(as_text=True).lower()
    assert Trek.query.count() == 0


def test_created_trek_is_open_by_default(client, seeded_users, login_as):
    form_data = valid_trek_data()
    form_data.pop("status")

    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        "/admin/trek/create",
        form_data,
    )

    created = Trek.query.one()
    assert response.status_code == 302
    assert created.status == "Open"
    assert created.available_slots == created.total_slots


def test_edit_trek_rejects_invalid_status(client, seeded_users, login_as, trek):
    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/edit/{trek.id}",
        valid_trek_data(status="Archived"),
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "status" in response.get_data(as_text=True).lower()
    assert trek.status == "Open"


def test_capacity_growth_preserves_occupied_slots(
    client, seeded_users, login_as, booking, trek
):
    assert trek.total_slots - trek.available_slots == 1

    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/edit/{trek.id}",
        valid_trek_data(total_slots="20"),
    )

    db.session.refresh(trek)
    assert response.status_code == 302
    assert trek.total_slots == 20
    assert trek.available_slots == 19


def test_capacity_below_occupied_slots_is_rejected(
    client, seeded_users, login_as, trek
):
    trek.available_slots = 2
    db.session.commit()

    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/edit/{trek.id}",
        valid_trek_data(total_slots="9"),
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "occupied" in response.get_data(as_text=True).lower()
    assert trek.total_slots == 12
    assert trek.available_slots == 2


@pytest.mark.parametrize("candidate", ["pending", "inactive", "trekker"])
def test_assignment_rejects_ineligible_user(
    client, seeded_users, login_as, trek, candidate
):
    if candidate == "pending":
        user = User(
            name="Pending Guide",
            email="pending@example.com",
            password="hash",
            role="staff",
            is_active=True,
            is_approved=False,
        )
        db.session.add(user)
        db.session.commit()
    elif candidate == "inactive":
        user = seeded_users["staff"]
        user.is_active = False
        db.session.commit()
    else:
        user = seeded_users["trekker"]
    trek.assigned_staff_id = None
    db.session.commit()

    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/assign_staff/{trek.id}",
        {"staff_id": str(user.id)},
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "eligible" in response.get_data(as_text=True).lower()
    assert trek.assigned_staff_id is None


def test_assignment_can_be_removed(client, seeded_users, login_as, trek):
    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/assign_staff/{trek.id}",
        {"staff_id": ""},
    )

    db.session.refresh(trek)
    assert response.status_code == 302
    assert trek.assigned_staff_id is None


def test_trek_with_booking_history_cannot_be_deleted(
    client, seeded_users, login_as, booking, trek
):
    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/delete/{trek.id}",
        follow_redirects=True,
    )

    assert "booking history" in response.get_data(as_text=True).lower()
    assert db.session.get(Trek, trek.id) is not None


def test_trek_without_history_can_be_deleted(
    client, seeded_users, login_as, trek
):
    trek_id = trek.id

    response = admin_post(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/trek/delete/{trek_id}",
    )

    assert response.status_code == 302
    assert db.session.get(Trek, trek_id) is None


@pytest.mark.parametrize("action", ["toggle", "approve"])
def test_admin_account_cannot_be_changed_by_user_actions(
    client, seeded_users, login_as, action
):
    admin = seeded_users["admin"]
    original_active = admin.is_active
    original_approved = admin.is_approved

    response = admin_post(
        client,
        login_as,
        admin,
        f"/admin/user/{action}/{admin.id}",
        follow_redirects=True,
    )

    db.session.refresh(admin)
    assert response.status_code == 200
    assert "administrator" in response.get_data(as_text=True).lower()
    assert admin.is_active == original_active
    assert admin.is_approved == original_approved


@pytest.mark.parametrize(
    "path",
    ["/admin/user/toggle/3", "/admin/user/approve/2"],
)
def test_admin_user_actions_reject_get(client, seeded_users, login_as, path):
    login_as(seeded_users["admin"])

    response = client.get(path)

    assert response.status_code == 405
