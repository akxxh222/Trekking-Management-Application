import pytest

from models import db


def staff_post(client, login_as, staff, path, data=None, follow_redirects=False):
    token = login_as(staff)
    payload = dict(data or {})
    payload["csrf_token"] = token
    return client.post(path, data=payload, follow_redirects=follow_redirects)


def test_assigned_staff_can_open_trek_detail(
    client, seeded_users, login_as, trek
):
    login_as(seeded_users["staff"])

    response = client.get(f"/staff/trek/{trek.id}")

    assert response.status_code == 200
    assert trek.name in response.get_data(as_text=True)


def test_unassigned_staff_cannot_open_trek_detail(
    client, seeded_users, login_as, trek
):
    trek.assigned_staff_id = None
    db.session.commit()
    login_as(seeded_users["staff"])

    response = client.get(f"/staff/trek/{trek.id}", follow_redirects=True)

    assert "not assigned" in response.get_data(as_text=True).lower()


def test_unassigned_staff_cannot_update_trek(
    client, seeded_users, login_as, trek
):
    trek.assigned_staff_id = None
    db.session.commit()

    response = staff_post(
        client,
        login_as,
        seeded_users["staff"],
        f"/staff/trek/{trek.id}/update",
        {"status": "Ongoing", "available_slots": "5"},
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "not assigned" in response.get_data(as_text=True).lower()
    assert trek.status == "Open"
    assert trek.available_slots == 12


def test_staff_rejects_unsupported_status(
    client, seeded_users, login_as, trek
):
    response = staff_post(
        client,
        login_as,
        seeded_users["staff"],
        f"/staff/trek/{trek.id}/update",
        {"status": "Archived", "available_slots": "5"},
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "valid trek status" in response.get_data(as_text=True).lower()
    assert trek.status == "Open"
    assert trek.available_slots == 12


@pytest.mark.parametrize(
    ("slots", "message"),
    [("many", "whole number"), ("-1", "zero"), ("13", "total")],
)
def test_staff_rejects_invalid_available_slots(
    client, seeded_users, login_as, trek, slots, message
):
    response = staff_post(
        client,
        login_as,
        seeded_users["staff"],
        f"/staff/trek/{trek.id}/update",
        {"status": "Ongoing", "available_slots": slots},
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert message in response.get_data(as_text=True).lower()
    assert trek.status == "Open"
    assert trek.available_slots == 12


def test_completed_trek_cannot_be_reopened(
    client, seeded_users, login_as, trek
):
    trek.status = "Completed"
    db.session.commit()

    response = staff_post(
        client,
        login_as,
        seeded_users["staff"],
        f"/staff/trek/{trek.id}/update",
        {"status": "Open", "available_slots": "12"},
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "cannot be reopened" in response.get_data(as_text=True).lower()
    assert trek.status == "Completed"


def test_staff_can_apply_valid_status_and_slot_update(
    client, seeded_users, login_as, trek
):
    response = staff_post(
        client,
        login_as,
        seeded_users["staff"],
        f"/staff/trek/{trek.id}/update",
        {"status": "Ongoing", "available_slots": "5"},
    )

    db.session.refresh(trek)
    assert response.status_code == 302
    assert trek.status == "Ongoing"
    assert trek.available_slots == 5


def test_staff_detail_renders_empty_participant_state_and_csrf_form(
    client, seeded_users, login_as, trek
):
    login_as(seeded_users["staff"])

    response = client.get(f"/staff/trek/{trek.id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No trekkers registered yet" in page
    assert 'name="csrf_token"' in page
