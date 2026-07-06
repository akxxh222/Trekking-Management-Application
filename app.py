from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Trek, Booking
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trekking_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# ─── Decorators ───────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') != role:
                flash('You do not have permission to access that page.')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─── Auth Routes ──────────────────────────────────────────────

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

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
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # 'trekker' or 'staff'

        # Admin cannot be registered
        if role == 'admin':
            flash('Admin registration is not allowed.')
            return redirect(url_for('register'))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists.')
            return redirect(url_for('register'))

        # Staff need approval, trekkers are auto-approved
        is_approved = True if role == 'trekker' else False

        new_user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role=role,
            is_active=True,
            is_approved=is_approved
        )

        db.session.add(new_user)
        db.session.commit()

        if role == 'staff':
            flash('Registration successful. Wait for admin approval before logging in.')
        else:
            flash('Registration successful. Please login.')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))


# ─── Dashboard Placeholder Routes ─────────────────────────────

# ─── Admin Routes ─────────────────────────────────────────────

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
        name = request.form['name']
        location = request.form['location']
        difficulty = request.form['difficulty']
        duration_days = int(request.form['duration_days'])
        total_slots = int(request.form['total_slots'])

        new_trek = Trek(
            name=name,
            location=location,
            difficulty=difficulty,
            duration_days=duration_days,
            total_slots=total_slots,
            available_slots=total_slots,
            status='Pending'
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
    trek = Trek.query.get_or_404(trek_id)

    if request.method == 'POST':
        trek.name = request.form['name']
        trek.location = request.form['location']
        trek.difficulty = request.form['difficulty']
        trek.duration_days = int(request.form['duration_days'])
        trek.total_slots = int(request.form['total_slots'])
        trek.status = request.form['status']

        db.session.commit()
        flash('Trek updated successfully.')
        return redirect(url_for('admin_treks'))

    return render_template('admin/trek_form.html', trek=trek)


@app.route('/admin/trek/delete/<int:trek_id>')
@login_required
@role_required('admin')
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    db.session.delete(trek)
    db.session.commit()
    flash('Trek deleted.')
    return redirect(url_for('admin_treks'))


@app.route('/admin/trek/assign_staff/<int:trek_id>', methods=['POST'])
@login_required
@role_required('admin')
def assign_staff(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_id = request.form.get('staff_id')
    trek.assigned_staff_id = int(staff_id) if staff_id else None
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


@app.route('/admin/user/toggle/<int:user_id>')
@login_required
@role_required('admin')
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.name} has been {status}.')
    return redirect(url_for('admin_users'))


@app.route('/admin/user/approve/<int:user_id>')
@login_required
@role_required('admin')
def approve_staff(user_id):
    user = User.query.get_or_404(user_id)
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


# ─── Staff Routes ──────────────────────────────────────────────

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
    trek = Trek.query.get_or_404(trek_id)

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


@app.route('/staff/trek/<int:trek_id>/update', methods=['POST'])
@login_required
@role_required('staff')
def staff_update_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != session['user_id']:
        flash('You are not assigned to this trek.')
        return redirect(url_for('staff_dashboard'))

    new_status = request.form.get('status')
    new_slots = request.form.get('available_slots')

    if new_status:
        trek.status = new_status

    if new_slots:
        trek.available_slots = int(new_slots)

    db.session.commit()
    flash('Trek updated successfully.')
    return redirect(url_for('staff_trek_detail', trek_id=trek_id))

@app.route('/staff/profile', methods=['GET', 'POST'])
@login_required
@role_required('staff')
def staff_profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.name = request.form['name']
        new_password = request.form.get('password')

        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()
        session['name'] = user.name  # Update navbar name immediately
        flash('Profile updated successfully.')
        return redirect(url_for('staff_profile'))

    return render_template('staff/profile.html', user=user)


# ─── User Routes ───────────────────────────────────────────────

@app.route('/user/dashboard')
@login_required
@role_required('trekker')
def user_dashboard():
    user = User.query.get(session['user_id'])

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


@app.route('/user/book/<int:trek_id>')
@login_required
@role_required('trekker')
def book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

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


@app.route('/user/cancel/<int:booking_id>')
@login_required
@role_required('trekker')
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    # Make sure this booking belongs to the logged-in user
    if booking.user_id != session['user_id']:
        flash('You cannot cancel this booking.')
        return redirect(url_for('my_bookings'))

    # Only allow cancelling active bookings
    if booking.status != 'Booked':
        flash('This booking cannot be cancelled.')
        return redirect(url_for('my_bookings'))

    booking.status = 'Cancelled'
    booking.trek.available_slots += 1  # Restore the slot

    db.session.commit()
    flash('Booking cancelled. Slot has been restored.')
    return redirect(url_for('my_bookings'))


@app.route('/user/profile', methods=['GET', 'POST'])
@login_required
@role_required('trekker')
def user_profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.name = request.form['name']
        new_password = request.form.get('password')

        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()
        session['name'] = user.name  # Update session name too
        flash('Profile updated successfully.')
        return redirect(url_for('user_profile'))

    return render_template('user/profile.html', user=user)


if __name__ == '__main__':
    app.run(debug=True)