import os
import re
import secrets

from flask import Flask, abort, render_template, request, redirect, url_for, session, flash
from models import db, User, Trek, Booking
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///trekking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


def csrf_token():
    token = session.get('csrf_token')
    if token is None:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


app.jinja_env.globals['csrf_token'] = csrf_token

TREK_DIFFICULTIES = ('Easy', 'Medium', 'Hard')
TREK_STATUSES = ('Pending', 'Open', 'Closed', 'Started', 'Ongoing', 'Completed')
BOOKING_STATUSES = ('Booked', 'Cancelled', 'Completed')


@app.before_request
def validate_csrf():
    if request.method != 'POST':
        return None

    expected = session.get('csrf_token')
    supplied = request.form.get('csrf_token', '')
    if not expected or not secrets.compare_digest(expected, supplied):
        abort(400, description='Invalid or missing CSRF token.')

    return None


# Decorators

def dashboard_endpoint(role):
    return {
        'admin': 'admin_dashboard',
        'staff': 'staff_dashboard',
        'trekker': 'user_dashboard',
    }.get(role, 'login')


def normalize_email(value):
    return (value or '').strip().lower()


def valid_email(value):
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value or ''))


def validate_account_form(form, registration):
    name = (form.get('name') or '').strip()
    password = form.get('password') or ''

    if not name:
        return None, 'Full name is required.'

    if password and len(password) < 8:
        return None, 'Password must be at least 8 characters.'

    data = {'name': name, 'password': password}
    if not registration:
        return data, None

    email = normalize_email(form.get('email'))
    role = (form.get('role') or '').strip().lower()
    if not valid_email(email):
        return None, 'Enter a valid email address.'
    if len(password) < 8:
        return None, 'Password must be at least 8 characters.'
    if role not in {'trekker', 'staff'}:
        return None, 'Choose a valid account role.'

    data.update(email=email, role=role)
    return data, None


def parse_positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, f'{field_name} must be a whole number.'
    if parsed <= 0:
        return None, f'{field_name} must be greater than zero.'
    return parsed, None


def validate_trek_form(form, trek=None):
    name = (form.get('name') or '').strip()
    location = (form.get('location') or '').strip()
    difficulty = form.get('difficulty') or ''

    if not name:
        return None, 'Trek name is required.'
    if not location:
        return None, 'Location is required.'
    if difficulty not in TREK_DIFFICULTIES:
        return None, 'Choose a valid difficulty.'

    duration_days, error = parse_positive_int(form.get('duration_days'), 'Duration')
    if error:
        return None, error
    total_slots, error = parse_positive_int(form.get('total_slots'), 'Total slots')
    if error:
        return None, error

    status = 'Pending'
    occupied_slots = 0
    if trek is not None:
        status = form.get('status') or ''
        if status not in TREK_STATUSES:
            return None, 'Choose a valid trek status.'
        occupied_slots = trek.total_slots - trek.available_slots
        if total_slots < occupied_slots:
            return None, 'Total slots cannot be lower than occupied slots.'

    return {
        'name': name,
        'location': location,
        'difficulty': difficulty,
        'duration_days': duration_days,
        'total_slots': total_slots,
        'available_slots': total_slots - occupied_slots,
        'status': status,
    }, None


def transition_booking_status(booking, new_status):
    if new_status not in BOOKING_STATUSES:
        return 'Choose a valid booking status.'
    if booking.status == new_status:
        return None

    trek = booking.trek
    if booking.status == 'Cancelled' and new_status != 'Cancelled':
        existing_booking = Booking.query.filter(
            Booking.id != booking.id,
            Booking.user_id == booking.user_id,
            Booking.trek_id == booking.trek_id,
            Booking.status != 'Cancelled',
        ).first()
        if existing_booking:
            return 'This trekker already has an active booking for this trek.'

    if booking.status != 'Cancelled' and new_status == 'Cancelled':
        if trek.available_slots >= trek.total_slots:
            return 'Trek capacity is already fully available.'
        trek.available_slots += 1
    elif booking.status == 'Cancelled' and new_status != 'Cancelled':
        if trek.available_slots <= 0:
            return 'No available slot remains for this booking.'
        trek.available_slots -= 1

    booking.status = new_status
    return None


def validate_staff_trek_update(trek, form):
    status = form.get('status') or ''
    if status not in TREK_STATUSES:
        return None, 'Choose a valid trek status.'
    if trek.status == 'Completed' and status != 'Completed':
        return None, 'A completed trek cannot be reopened.'

    try:
        available_slots = int(form.get('available_slots'))
    except (TypeError, ValueError):
        return None, 'Available slots must be a whole number.'
    if available_slots < 0:
        return None, 'Available slots must be zero or greater.'
    if available_slots > trek.total_slots:
        return None, 'Available slots cannot exceed total slots.'

    return {'status': status, 'available_slots': available_slots}, None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))

        user = db.session.get(User, session['user_id'])
        account_unavailable = (
            user is None
            or not user.is_active
            or (user.role == 'staff' and not user.is_approved)
        )
        if account_unavailable:
            session.clear()
            flash('Your account is no longer available. Please contact an administrator.')
            return redirect(url_for('login'))

        session['role'] = user.role
        session['name'] = user.name
        return f(*args, **kwargs)
    return decorated


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') != role:
                flash('You do not have permission to access that page.')
                return redirect(url_for(dashboard_endpoint(session.get('role'))))
            return f(*args, **kwargs)
        return decorated
    return decorator


# Auth Routes

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = normalize_email(request.form.get('email'))
        password = request.form.get('password', '')

        user = User.query.filter(db.func.lower(User.email) == email).first()

        if not user:
            flash('No account found with that email.')
            return redirect(url_for('login'))

        if not check_password_hash(user.password, password):
            flash('Incorrect password.')
            return redirect(url_for('login'))

        if not user.is_active:
            flash('Your account has been deactivated. Contact admin.')
            return redirect(url_for('login'))

        if user.role == 'staff' and not user.is_approved:
            flash('Your staff account is pending admin approval.')
            return redirect(url_for('login'))

        # Store user info in session
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name

        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data, error = validate_account_form(request.form, registration=True)
        if error:
            flash(error)
            role = request.form.get('role')
            return redirect(url_for(
                'register',
                name=(request.form.get('name') or '').strip(),
                email=normalize_email(request.form.get('email')),
                role=role if role in {'trekker', 'staff'} else 'trekker'
            ))

        existing = User.query.filter(db.func.lower(User.email) == data['email']).first()
        if existing:
            flash('An account with this email already exists.')
            return redirect(url_for(
                'register', name=data['name'], email=data['email'], role=data['role']
            ))

        # Staff need approval, trekkers are auto-approved
        is_approved = data['role'] == 'trekker'

        new_user = User(
            name=data['name'],
            email=data['email'],
            password=generate_password_hash(data['password']),
            role=data['role'],
            is_active=True,
            is_approved=is_approved
        )

        db.session.add(new_user)
        db.session.commit()

        if data['role'] == 'staff':
            flash('Registration successful. Wait for admin approval before logging in.')
        else:
            flash('Registration successful. Please login.')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))


# Admin Routes

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    total_treks = Trek.query.count()
    total_users = User.query.filter_by(role='trekker').count()
    total_staff = User.query.filter_by(role='staff').count()
    total_bookings = Booking.query.count()
    pending_staff = User.query.filter_by(role='staff', is_approved=False).count()

    return render_template('admin/dashboard.html',
        total_treks=total_treks,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        pending_staff=pending_staff
    )


@app.route('/admin/treks')
@login_required
@role_required('admin')
def admin_treks():
    search = request.args.get('search', '')
    if search:
        treks = Trek.query.filter(Trek.name.contains(search)).all()
    else:
        treks = Trek.query.all()

    staff_list = User.query.filter_by(role='staff', is_approved=True, is_active=True).all()
    return render_template('admin/treks.html', treks=treks, staff_list=staff_list, search=search)


@app.route('/admin/trek/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_trek():
    if request.method == 'POST':
        data, error = validate_trek_form(request.form)
        if error:
            flash(error)
            return redirect(url_for('create_trek'))

        new_trek = Trek(
            **data
        )
        db.session.add(new_trek)
        db.session.commit()
        flash('Trek created successfully.')
        return redirect(url_for('admin_treks'))

    return render_template('admin/trek_form.html', trek=None)


@app.route('/admin/trek/edit/<int:trek_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_trek(trek_id):
    trek = db.get_or_404(Trek, trek_id)

    if request.method == 'POST':
        data, error = validate_trek_form(request.form, trek)
        if error:
            flash(error)
            return redirect(url_for('edit_trek', trek_id=trek.id))

        for field, value in data.items():
            setattr(trek, field, value)

        db.session.commit()
        flash('Trek updated successfully.')
        return redirect(url_for('admin_treks'))

    return render_template('admin/trek_form.html', trek=trek)


@app.route('/admin/trek/delete/<int:trek_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_trek(trek_id):
    trek = db.get_or_404(Trek, trek_id)
    if trek.bookings:
        flash('This trek has booking history and cannot be deleted.')
        return redirect(url_for('admin_treks'))

    db.session.delete(trek)
    db.session.commit()
    flash('Trek deleted.')
    return redirect(url_for('admin_treks'))


@app.route('/admin/trek/assign_staff/<int:trek_id>', methods=['POST'])
@login_required
@role_required('admin')
def assign_staff(trek_id):
    trek = db.get_or_404(Trek, trek_id)
    staff_id = request.form.get('staff_id')
    if not staff_id:
        trek.assigned_staff_id = None
    else:
        try:
            staff_id = int(staff_id)
        except (TypeError, ValueError):
            flash('Choose an eligible staff member.')
            return redirect(url_for('admin_treks'))

        staff = db.session.get(User, staff_id)
        if not staff or staff.role != 'staff' or not staff.is_active or not staff.is_approved:
            flash('Choose an eligible active, approved staff member.')
            return redirect(url_for('admin_treks'))
        trek.assigned_staff_id = staff.id
    db.session.commit()
    flash('Staff assigned successfully.')
    return redirect(url_for('admin_treks'))


@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    search = request.args.get('search', '')
    if search:
        users = User.query.filter(
            User.role != 'admin',
            User.name.contains(search)
        ).all()
    else:
        users = User.query.filter(User.role != 'admin').all()

    return render_template('admin/users.html', users=users, search=search)


@app.route('/admin/user/toggle/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == 'admin':
        flash('Administrator accounts cannot be changed here.')
        return redirect(url_for('admin_users'))

    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} has been {status}.')
    return redirect(url_for('admin_users'))


@app.route('/admin/user/approve/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def approve_staff(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == 'admin':
        flash('Administrator accounts cannot be changed here.')
        return redirect(url_for('admin_users'))
    if user.role != 'staff':
        flash('Only staff accounts can be approved.')
        return redirect(url_for('admin_users'))

    user.is_approved = True
    db.session.commit()
    flash(f'{user.name} has been approved as trek staff.')
    return redirect(url_for('admin_users'))


@app.route('/admin/bookings')
@login_required
@role_required('admin')
def admin_bookings():
    bookings = Booking.query.all()
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/admin/booking/update/<int:booking_id>', methods=['POST'])
@login_required
@role_required('admin')
def update_booking_status(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    new_status = request.form.get('status')

    error = transition_booking_status(booking, new_status)
    if error:
        flash(error)
        return redirect(url_for('admin_bookings'))

    db.session.commit()
    flash('Booking status updated.')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/charts')
@login_required
@role_required('admin')
def admin_charts():
    # Total treks by status
    statuses = ['Pending', 'Open', 'Closed', 'Started', 'Ongoing', 'Completed']
    trek_counts = [Trek.query.filter_by(status=s).count() for s in statuses]

    # Bookings per day (last 7 days)
    from datetime import datetime, timedelta
    dates = []
    booking_counts = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        day_str = str(day)
        count = Booking.query.filter_by(booking_date=day_str).count()
        dates.append(day.strftime('%d %b'))
        booking_counts.append(count)

    # Active users (trekkers with at least one booking)
    from sqlalchemy import func
    active_users = db.session.query(Booking.user_id).distinct().count()
    total_trekkers = User.query.filter_by(role='trekker').count()
    inactive_users = total_trekkers - active_users

    return render_template('admin/charts.html',
        statuses=statuses,
        trek_counts=trek_counts,
        dates=dates,
        booking_counts=booking_counts,
        active_users=active_users,
        inactive_users=inactive_users
    )


# Staff Routes

@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    # Staff can only see treks assigned to them
    assigned_treks = Trek.query.filter_by(assigned_staff_id=session['user_id']).all()

    return render_template('staff/dashboard.html',
        assigned_treks=assigned_treks
    )


@app.route('/staff/trek/<int:trek_id>')
@login_required
@role_required('staff')
def staff_trek_detail(trek_id):
    trek = db.get_or_404(Trek, trek_id)

    # Make sure this staff is actually assigned to this trek
    if trek.assigned_staff_id != session['user_id']:
        flash('You are not assigned to this trek.')
        return redirect(url_for('staff_dashboard'))

    # Get all bookings for this trek
    bookings = Booking.query.filter_by(trek_id=trek_id).all()

    return render_template('staff/trek_detail.html',
        trek=trek,
        bookings=bookings
    )

@app.route('/staff/profile', methods=['GET', 'POST'])
@login_required
@role_required('staff')
def staff_profile():
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        data, error = validate_account_form(request.form, registration=False)
        if error:
            flash(error)
            return redirect(url_for('staff_profile'))

        user.name = data['name']
        if data['password']:
            user.password = generate_password_hash(data['password'])

        db.session.commit()
        session['name'] = user.name  # Update navbar name immediately
        flash('Profile updated successfully.')
        return redirect(url_for('staff_profile'))

    return render_template('staff/profile.html', user=user)

@app.route('/staff/trek/<int:trek_id>/update', methods=['POST'])
@login_required
@role_required('staff')
def staff_update_trek(trek_id):
    trek = db.get_or_404(Trek, trek_id)

    if trek.assigned_staff_id != session['user_id']:
        flash('You are not assigned to this trek.')
        return redirect(url_for('staff_dashboard'))

    data, error = validate_staff_trek_update(trek, request.form)
    if error:
        flash(error)
        return redirect(url_for('staff_trek_detail', trek_id=trek_id))

    trek.status = data['status']
    trek.available_slots = data['available_slots']

    db.session.commit()
    flash('Trek updated successfully.')
    return redirect(url_for('staff_trek_detail', trek_id=trek_id))

@app.route('/staff/charts')
@login_required
@role_required('staff')
def staff_charts():
    assigned_treks = Trek.query.filter_by(assigned_staff_id=session['user_id']).all()

    trek_names = []
    participant_counts = []
    slot_remaining = []

    for trek in assigned_treks:
        trek_names.append(trek.name)
        count = Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
        participant_counts.append(count)
        slot_remaining.append(trek.available_slots)

    return render_template('staff/charts.html',
        trek_names=trek_names,
        participant_counts=participant_counts,
        slot_remaining=slot_remaining
    )


# User Routes

@app.route('/user/dashboard')
@login_required
@role_required('trekker')
def user_dashboard():
    user = db.session.get(User, session['user_id'])

    # Count this user's bookings
    total_bookings = Booking.query.filter_by(user_id=session['user_id']).count()
    active_bookings = Booking.query.filter_by(
        user_id=session['user_id'],
        status='Booked'
    ).count()

    return render_template('user/dashboard.html',
        user=user,
        total_bookings=total_bookings,
        active_bookings=active_bookings
    )


@app.route('/user/treks')
@login_required
@role_required('trekker')
def user_treks():
    search = request.args.get('search', '')
    difficulty = request.args.get('difficulty', '')
    location = request.args.get('location', '')  

    query = Trek.query.filter_by(status='Open')

    if search:
        query = query.filter(Trek.name.contains(search))

    if difficulty:
        query = query.filter_by(difficulty=difficulty)

    if location:                                          
        query = query.filter(Trek.location.contains(location))

    treks = query.all()

    user_bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    booked_trek_ids = [b.trek_id for b in user_bookings if b.status == 'Booked']

    return render_template('user/treks.html',
        treks=treks,
        booked_trek_ids=booked_trek_ids,
        search=search,
        difficulty=difficulty,
        location=location      
    )


@app.route('/user/book/<int:trek_id>', methods=['POST'])
@login_required
@role_required('trekker')
def book_trek(trek_id):
    trek = db.get_or_404(Trek, trek_id)

    # Check 1: Trek must be Open
    if trek.status != 'Open':
        flash('This trek is not open for booking.')
        return redirect(url_for('user_treks'))

    # Check 2: Slots must be available
    if trek.available_slots <= 0:
        flash('No slots available for this trek.')
        return redirect(url_for('user_treks'))

    # Check 3: User must not have already booked this trek
    existing = Booking.query.filter_by(
        user_id=session['user_id'],
        trek_id=trek_id,
        status='Booked'
    ).first()

    if existing:
        flash('You have already booked this trek.')
        return redirect(url_for('user_treks'))

    # All checks passed — create the booking
    new_booking = Booking(
        user_id=session['user_id'],
        trek_id=trek_id,
        booking_date=str(date.today()),
        status='Booked',
        payment_status='Paid'
    )

    trek.available_slots -= 1  # Reduce available slots by 1

    db.session.add(new_booking)
    db.session.commit()

    flash(f'Successfully booked {trek.name}!')
    return redirect(url_for('my_bookings'))


@app.route('/user/bookings')
@login_required
@role_required('trekker')
def my_bookings():
    bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    return render_template('user/my_bookings.html', bookings=bookings)


@app.route('/user/cancel/<int:booking_id>', methods=['POST'])
@login_required
@role_required('trekker')
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)

    # Make sure this booking belongs to the logged-in user
    if booking.user_id != session['user_id']:
        flash('You cannot cancel this booking.')
        return redirect(url_for('my_bookings'))

    # Only allow cancelling active bookings
    if booking.status != 'Booked':
        flash('This booking cannot be cancelled.')
        return redirect(url_for('my_bookings'))

    error = transition_booking_status(booking, 'Cancelled')
    if error:
        flash(error)
        return redirect(url_for('my_bookings'))

    db.session.commit()
    flash('Booking cancelled. Slot has been restored.')
    return redirect(url_for('my_bookings'))


@app.route('/user/profile', methods=['GET', 'POST'])
@login_required
@role_required('trekker')
def user_profile():
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        data, error = validate_account_form(request.form, registration=False)
        if error:
            flash(error)
            return redirect(url_for('user_profile'))

        user.name = data['name']
        if data['password']:
            user.password = generate_password_hash(data['password'])

        db.session.commit()
        session['name'] = user.name  # Update session name too
        flash('Profile updated successfully.')
        return redirect(url_for('user_profile'))

    return render_template('user/profile.html', user=user)

@app.route('/user/history')
@login_required
@role_required('trekker')
def trekking_history():
    # Active bookings - currently booked
    active = Booking.query.filter_by(
        user_id=session['user_id'],
        status='Booked'
    ).all()

    # Past bookings - completed or cancelled
    past = Booking.query.filter(
        Booking.user_id == session['user_id'],
        Booking.status.in_(['Completed', 'Cancelled'])
    ).all()

    return render_template('user/history.html', active=active, past=past)

@app.route('/user/charts')
@login_required
@role_required('trekker')
def user_charts():
    bookings = Booking.query.filter_by(user_id=session['user_id']).all()

    # Booking status breakdown
    booked = sum(1 for b in bookings if b.status == 'Booked')
    completed = sum(1 for b in bookings if b.status == 'Completed')
    cancelled = sum(1 for b in bookings if b.status == 'Cancelled')

    # Difficulty breakdown of all booked treks
    difficulties = {'Easy': 0, 'Medium': 0, 'Hard': 0}
    for b in bookings:
        diff = b.trek.difficulty
        if diff in difficulties:
            difficulties[diff] += 1

    return render_template('user/charts.html',
        booked=booked,
        completed=completed,
        cancelled=cancelled,
        difficulties=list(difficulties.keys()),
        diff_counts=list(difficulties.values())
    )

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)


