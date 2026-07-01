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


@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    return f"Welcome Staff: {session['name']} — Dashboard coming"


@app.route('/user/dashboard')
@login_required
@role_required('trekker')
def user_dashboard():
    return f"Welcome Trekker: {session['name']} — Dashboard coming"


if __name__ == '__main__':
    app.run(debug=True)