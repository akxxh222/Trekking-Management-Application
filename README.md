# Trekking Management Application

A web-based trek management platform built with **Flask** that enables trekkers to explore and book treks, trek staff to manage assigned treks, and administrators to oversee the entire platform.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Database | SQLite via Flask-SQLAlchemy |
| Authentication | Werkzeug (password hashing, session-based) |
| Frontend | Bootstrap 5.3, Jinja2 Templates |
| Charts | Chart.js (CDN) |
| Styling | Custom dark theme (CSS) |

---

## Installation & Setup

### Prerequisites

- Python 3.12+
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/Trekking-Management-Application.git
cd Trekking-Management-Application

# 2. Install dependencies
pip install flask flask-sqlalchemy werkzeug

# 3. Create the admin user (optional)
python create_admin.py

# 4. Run the application
python app.py
```

The app will start at **http://127.0.0.1:5000**

---

## Default Admin Credentials

| Field | Value |
|-------|-------|
| Email | `admin@trek.com` |
| Password | `admin123` |

Run `python create_admin.py` to seed this admin account.

---

## Project Structure

```
Trekking-Management-Application/
├── app.py                    # Main Flask app — routes, auth, decorators
├── models.py                 # SQLAlchemy models (User, Trek, Booking)
├── create_admin.py           # Seeds default admin account
├── requirements.txt          # Python dependencies
├── templates/
│   ├── base.html             # Master layout — navbar, theme, flash messages
│   ├── login.html            # Login form
│   ├── register.html         # Registration form
│   ├── admin/
│   │   ├── dashboard.html    # Admin dashboard with stats cards
│   │   ├── treks.html        # Trek management table
│   │   ├── trek_form.html    # Create/Edit trek form
│   │   ├── users.html        # User & staff management table
│   │   ├── bookings.html     # All bookings with status update
│   │   └── charts.html       # Analytics charts
│   ├── staff/
│   │   ├── dashboard.html    # Assigned treks overview
│   │   ├── trek_detail.html  # Trek detail with update form
│   │   ├── profile.html      # Staff profile edit
│   │   └── charts.html       # Staff analytics charts
│   └── user/
│       ├── dashboard.html    # User dashboard with stats
│       ├── treks.html        # Browse and filter open treks
│       ├── my_bookings.html  # User's bookings table
│       ├── profile.html      # User profile edit
│       ├── history.html      # Trekking history (active + past)
│       └── charts.html       # Personal stats charts
└── instance/
    └── trekking.db           # SQLite database (auto-created)
```

---

## Database Models

### User

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | Primary key |
| `name` | String(100) | Required |
| `email` | String(100) | Unique, required |
| `password` | String(200) | Hashed via Werkzeug |
| `role` | String(20) | `admin`, `staff`, or `trekker` |
| `is_active` | Boolean | Default: `True` |
| `is_approved` | Boolean | Default: `False` (for staff approval) |

### Trek

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | Primary key |
| `name` | String(100) | Required |
| `location` | String(100) | Required |
| `difficulty` | String(20) | `Easy`, `Medium`, `Hard` |
| `duration_days` | Integer | Required |
| `total_slots` | Integer | Required |
| `available_slots` | Integer | Required |
| `status` | String(20) | `Pending`, `Open`, `Closed`, `Started`, `Ongoing`, `Completed` |
| `assigned_staff_id` | Integer | ForeignKey to `User.id` |

### Booking

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | Primary key |
| `user_id` | Integer | ForeignKey to `User.id` |
| `trek_id` | Integer | ForeignKey to `Trek.id` |
| `booking_date` | String(20) | Date string (e.g. `2026-07-14`) |
| `status` | String(20) | `Booked`, `Cancelled`, `Completed` |
| `payment_status` | String(20) | Default: `Paid` |

---

## Routes Overview

### Public Routes

| Route | Methods | Description |
|-------|---------|-------------|
| `/` | GET | Redirects to `/login` |
| `/login` | GET, POST | Authenticates user by email/password |
| `/register` | GET, POST | Registers a new user |
| `/logout` | GET | Clears session |

### Admin Routes (requires `admin` role)

| Route | Methods | Description |
|-------|---------|-------------|
| `/admin/dashboard` | GET | Stats overview |
| `/admin/treks` | GET | Trek list with search |
| `/admin/trek/create` | GET, POST | Create a trek |
| `/admin/trek/edit/<id>` | GET, POST | Edit a trek |
| `/admin/trek/delete/<id>` | GET | Delete a trek |
| `/admin/trek/assign_staff/<id>` | POST | Assign staff to trek |
| `/admin/users` | GET | User list with search |
| `/admin/user/toggle/<id>` | GET | Activate/deactivate user |
| `/admin/user/approve/<id>` | GET | Approve staff registration |
| `/admin/bookings` | GET | All bookings |
| `/admin/booking/update/<id>` | POST | Update booking status |
| `/admin/charts` | GET | Analytics charts |

### Staff Routes (requires `staff` role)

| Route | Methods | Description |
|-------|---------|-------------|
| `/staff/dashboard` | GET | Assigned treks |
| `/staff/trek/<id>` | GET | Trek detail + registered trekkers |
| `/staff/trek/<id>/update` | POST | Update status/slots |
| `/staff/profile` | GET, POST | Edit profile |
| `/staff/charts` | GET | Analytics charts |

### User Routes (requires `trekker` role)

| Route | Methods | Description |
|-------|---------|-------------|
| `/user/dashboard` | GET | Personal dashboard |
| `/user/treks` | GET | Browse open treks with filters |
| `/user/book/<id>` | GET | Book a trek |
| `/user/bookings` | GET | My bookings |
| `/user/cancel/<id>` | GET | Cancel a booking |
| `/user/profile` | GET, POST | Edit profile |
| `/user/history` | GET | Trekking history |
| `/user/charts` | GET | Personal stats charts |

---

## Role Permissions

### Admin
- Create, edit, delete treks
- Assign staff to treks
- Activate/deactivate users
- Approve staff registrations
- View and update all bookings
- View platform-wide analytics

### Staff
- View only assigned treks
- Update trek status and available slots
- View registered trekkers for assigned treks
- Cannot reopen a completed trek
- Edit own profile

### Trekker (User)
- Browse and filter open treks
- Book treks (with duplicate/full/closed prevention)
- Cancel own bookings
- View booking history
- Edit own profile
- View personal booking stats

---

## Features

### Authentication & Authorization
- Session-based login with role-based access control
- Password hashing via Werkzeug
- Staff registration requires admin approval

### Trek Management
- Admin: full CRUD operations
- Staff: update assigned trek status and slots
- Status workflow: Pending → Open → Closed → Started → Ongoing → Completed
- Completed treks cannot be reopened

### Booking System
- Three validation checks: trek must be Open, slots available, no duplicate booking
- Auto-decrements available slots on booking
- Cancel restores the slot
- Admin can override booking status

### Charts & Analytics
- Admin: treks by status, active vs inactive trekkers, bookings over 7 days
- Staff: participants per trek, slots remaining per trek
- User: booking status breakdown, treks by difficulty

### Responsive UI
- Dark navy theme with Bootstrap 5.3
- Mobile-responsive grids (`col-6 col-md-3`, etc.)
- Role-aware navigation bar
- Search and filter functionality
- Flash message notifications

---

## Issues Encountered & Fixes

### 1. Jinja2 TemplateSyntaxError
**Problem:** Missing whitespace in Jinja2 tags caused the template engine to fail.
- `{%extends 'base.html' %}` → fixed to `{% extends 'base.html' %}`
- `{%block content %}` → fixed to `{% block content %}`
- `{% if session.get('name')%}` → fixed to `{% if session.get('name') %}`

### 2. Stray HTML Tag in login.html
**Problem:** An extra `</form>` closing tag after the `<p>` paragraph broke the HTML structure, preventing form submission.
**Fix:** Removed the orphaned `</form>` tag.

### 3. Typo in base.html Button Class
**Problem:** `class="'btn btn-outline-light btn-sm"` had a stray single quote before `btn`, making the Bootstrap class invalid.
**Fix:** Removed the extra quote.

### 4. Duplicate Route Endpoint
**Problem:** Two `staff_update_trek` functions with the same route `/staff/trek/<int:trek_id>/update` caused Flask to crash on startup with an `AssertionError` (duplicate endpoint).
**Fix:** Removed the duplicate function definition, keeping only the version with the completed-trek guard logic.

### 5. Dark Theme Text Visibility
**Problem:** After switching to a dark navy theme (`#0f172a` background, `#1e293b` cards), text and UI elements were invisible:
- Chart colors (`#343a40`) blended into card backgrounds
- `btn-outline-dark` and `btn-outline-secondary` had dark text/borders that disappeared
- Form select dropdown arrows were dark
- Dropdown option lists had white backgrounds with light text
- Chart gridlines and tick labels were invisible
**Fixes:** Updated chart colors to light blues/greens, added explicit button backgrounds matching the card color, replaced form-select arrow with a light SVG, styled dropdown options, and added chart scale color configs.

### 6. Login Box Sizing
**Problem:** The login card spanned full width because it lacked a `col-md-5` grid wrapper, making it much larger than the register card.
**Fix:** Added `col-md-5` wrapper to the login card to match the register page layout.

### 7. Form Select & Outline Button Visibility
**Problem:** Form controls had `#0f172a` background which didn't match the `#1e293b` card background, and dropdown options inherited system default (white) background making text unreadable.
**Fixes:** Unified form background to `#1e293b`, added explicit `option` styling, and added `background: #1e293b` to outline buttons with white text.
