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

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    return f"Welcome Admin: {session['name']} — Dashboard coming"


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