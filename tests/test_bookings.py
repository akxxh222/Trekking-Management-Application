import pytest

from models import Booking, User, db


def post_as(client, login_as, user, path, data=None, follow_redirects=False):
    token = login_as(user)
    payload = dict(data or {})
    payload["csrf_token"] = token
    return client.post(path, data=payload, follow_redirects=follow_redirects)


def test_successful_booking_creates_record_and_uses_one_slot(
    client, seeded_users, login_as, trek
):
    response = post_as(
        client,
        login_as,
        seeded_users["trekker"],
        f"/user/book/{trek.id}",
    )

    db.session.refresh(trek)
    created = Booking.query.filter_by(
        user_id=seeded_users["trekker"].id, trek_id=trek.id
    ).one()
    assert response.status_code == 302
    assert created.status == "Booked"
    assert trek.available_slots == 11


def test_duplicate_active_booking_does_not_use_another_slot(
    client, seeded_users, login_as, booking, trek
):
    response = post_as(
        client,
        login_as,
        seeded_users["trekker"],
        f"/user/book/{trek.id}",
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert "already booked" in response.get_data(as_text=True).lower()
    assert Booking.query.filter_by(trek_id=trek.id).count() == 1
    assert trek.available_slots == 11


@pytest.mark.parametrize(("status", "slots", "message"), [("Closed", 12, "not open"), ("Open", 0, "no slots")])
def test_unavailable_trek_cannot_be_booked(
    client, seeded_users, login_as, trek, status, slots, message
):
    trek.status = status
    trek.available_slots = slots
    db.session.commit()

    response = post_as(
        client,
        login_as,
        seeded_users["trekker"],
        f"/user/book/{trek.id}",
        follow_redirects=True,
    )

    db.session.refresh(trek)
    assert message in response.get_data(as_text=True).lower()
    assert Booking.query.count() == 0
    assert trek.available_slots == slots


def test_owner_can_cancel_once_and_restore_one_slot(
    client, seeded_users, login_as, booking, trek
):
    response = post_as(
        client,
        login_as,
        seeded_users["trekker"],
        f"/user/cancel/{booking.id}",
    )

    db.session.refresh(booking)
    db.session.refresh(trek)
    assert response.status_code == 302
    assert booking.status == "Cancelled"
    assert trek.available_slots == 12


def test_other_trekker_cannot_cancel_booking(
    client, seeded_users, login_as, booking, trek
):
    other = User(
        name="Other Trekker",
        email="other@example.com",
        password="hash",
        role="trekker",
        is_active=True,
        is_approved=True,
    )
    db.session.add(other)
    db.session.commit()

    response = post_as(
        client,
        login_as,
        other,
        f"/user/cancel/{booking.id}",
        follow_redirects=True,
    )

    db.session.refresh(booking)
    db.session.refresh(trek)
    assert "cannot cancel" in response.get_data(as_text=True).lower()
    assert booking.status == "Booked"
    assert trek.available_slots == 11


def test_repeated_cancellation_does_not_restore_another_slot(
    client, seeded_users, login_as, booking, trek
):
    path = f"/user/cancel/{booking.id}"
    post_as(client, login_as, seeded_users["trekker"], path)
    response = post_as(
        client, login_as, seeded_users["trekker"], path, follow_redirects=True
    )

    db.session.refresh(trek)
    assert "cannot be cancelled" in response.get_data(as_text=True).lower()
    assert trek.available_slots == 12


def test_admin_cancel_and_rebook_reconcile_one_slot(
    client, seeded_users, login_as, booking, trek
):
    path = f"/admin/booking/update/{booking.id}"
    post_as(client, login_as, seeded_users["admin"], path, {"status": "Cancelled"})
    db.session.refresh(trek)
    assert trek.available_slots == 12

    post_as(client, login_as, seeded_users["admin"], path, {"status": "Booked"})
    db.session.refresh(booking)
    db.session.refresh(trek)
    assert booking.status == "Booked"
    assert trek.available_slots == 11


def test_admin_no_op_status_does_not_change_slots(
    client, seeded_users, login_as, booking, trek
):
    response = post_as(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/booking/update/{booking.id}",
        {"status": "Booked"},
    )

    db.session.refresh(trek)
    assert response.status_code == 302
    assert trek.available_slots == 11


def test_admin_rejects_invalid_booking_status(
    client, seeded_users, login_as, booking, trek
):
    response = post_as(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/booking/update/{booking.id}",
        {"status": "Refunded"},
        follow_redirects=True,
    )

    db.session.refresh(booking)
    db.session.refresh(trek)
    assert "valid booking status" in response.get_data(as_text=True).lower()
    assert booking.status == "Booked"
    assert trek.available_slots == 11


def test_admin_cancellation_cannot_exceed_total_capacity(
    client, seeded_users, login_as, booking, trek
):
    trek.available_slots = trek.total_slots
    db.session.commit()

    response = post_as(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/booking/update/{booking.id}",
        {"status": "Cancelled"},
        follow_redirects=True,
    )

    db.session.refresh(booking)
    db.session.refresh(trek)
    assert "capacity" in response.get_data(as_text=True).lower()
    assert booking.status == "Booked"
    assert trek.available_slots == trek.total_slots


def test_admin_reactivation_requires_available_slot(
    client, seeded_users, login_as, booking, trek
):
    booking.status = "Cancelled"
    trek.available_slots = 0
    db.session.commit()

    response = post_as(
        client,
        login_as,
        seeded_users["admin"],
        f"/admin/booking/update/{booking.id}",
        {"status": "Booked"},
        follow_redirects=True,
    )

    db.session.refresh(booking)
    db.session.refresh(trek)
    assert "available slot" in response.get_data(as_text=True).lower()
    assert booking.status == "Cancelled"
    assert trek.available_slots == 0
