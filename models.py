from flask_sqlalchemy import SQLAlchemy

db=SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Store the password hash.
    role = db.Column(db.String(7), nullable=False)  # 'admin', 'staff', 'trekker'
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)  # only matters for staff

    bookings = db.relationship('Booking', backref='trekker', lazy=True)


class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), nullable=False)
    location = db.Column(db.String(25), nullable=False)
    difficulty = db.Column(db.String(6), nullable=False)  # Easy, Medium, Hard
    duration_days = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(9), default='Pending')  # Pending, Open, Closed, Ongoing, Completed
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    bookings = db.relationship('Booking', backref='trek', lazy=True)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'), nullable=False)
    booking_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    status = db.Column(db.String(9), default='Booked')  # Booked, Cancelled, Completed
    payment_status = db.Column(db.String(10), default='Paid')
