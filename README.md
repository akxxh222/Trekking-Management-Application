# TrekSphere

TrekSphere is a Flask application for running trekking operations. Trekkers can discover and book routes, field staff can manage assigned treks, and administrators can coordinate people, capacity, bookings, and reporting from one responsive interface.

## What it includes

- Session-based authentication for administrators, field staff, and trekkers
- Staff approval and account access controls
- Trek creation, capacity management, status updates, and staff assignment
- Safe booking and cancellation with exact slot accounting
- Role-specific dashboards, history, and Chart.js insights
- CSRF-protected forms and server-side input validation
- Responsive, accessible interface designed for desktop and mobile
- Automated route, permission, business-rule, and template tests

## Technology

- Python 3.12
- Flask 3.0.3
- Flask-SQLAlchemy 3.1.1
- SQLite
- Jinja templates and Bootstrap 5.3
- Chart.js
- pytest 8.3.2

## Local setup

Create and activate a virtual environment from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set a unique secret key for local sessions. The application has a development fallback so it can start without this variable, but that fallback must never be used for a deployed instance.

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-value"
```

The default database is stored at `instance/trekking.db`. To use a different database URL, set `DATABASE_URL` before starting the app.

Create the initial administrator, then run the server:

```powershell
python create_admin.py
python app.py
```

Open `http://127.0.0.1:5000`.

The Flask development server runs with debug diagnostics enabled and the automatic file reloader disabled. This avoids repeated watchdog restarts caused by unrelated changes in global Python packages. Do not use the development server in production.

## Initial administrator

`create_admin.py` creates this local account when it does not already exist:

- Email: `admin@trek.com`
- Password: `admin123`

Change this password before using the application with real or shared data.

## Test suite

Run all automated checks from the repository root:

```powershell
pytest -q
```

The suite uses an isolated in-memory SQLite database. It does not modify `instance/trekking.db`.

For a quick Python syntax check:

```powershell
python -m compileall -q app.py models.py create_admin.py
```

## Role workflows

### Administrator

- Review platform totals and pending staff accounts
- Create and edit treks without corrupting occupied capacity
- Assign only active, approved staff members
- Protect treks that already have booking history
- Activate or deactivate non-admin accounts
- Reconcile booking states and available places
- View operational insights

### Field staff

- View only assigned treks
- Update valid trek states and bounded available capacity
- Review the participant manifest
- Keep completed treks closed
- Update profile information and review field insights

### Trekker

- Search open treks by name, location, and difficulty
- Book one active place per trek
- Cancel only an owned, active booking
- Review bookings, trail history, and personal insights
- Update profile information

## Security behavior

- Every state-changing request uses POST and a session-bound CSRF token.
- Email addresses are normalized before registration and login.
- Submitted roles, status values, IDs, and numeric limits are validated server-side.
- Passwords are hashed with Werkzeug.
- The secret key can be provided through `SECRET_KEY`.
- Capacity changes and booking status transitions are committed together.

This is still a learning-oriented application. A production deployment should add a production WSGI server, HTTPS, secure cookie settings, secret management, database migrations, monitoring, and administrator password rotation.

## Repository structure

```text
.
|-- app.py                         Flask routes, validation, and application setup
|-- models.py                      User, Trek, and Booking models
|-- create_admin.py                Initial administrator setup
|-- requirements.txt               Pinned direct dependencies
|-- static/
|   |-- css/app.css                Shared visual system
|   `-- js/app.js                  Progressive form confirmations
|-- templates/
|   |-- base.html                  Shared application shell
|   |-- login.html
|   |-- register.html
|   |-- admin/                     Administrator pages
|   |-- staff/                     Field staff pages
|   `-- user/                      Trekker pages
|-- tests/                         Isolated automated test suite
|-- docs/superpowers/              Approved design and implementation plan
`-- instance/                      Local SQLite data, ignored by Git
```
