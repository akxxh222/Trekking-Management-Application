from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    existing = User.query.filter_by(email='admin@trek.com').first()

    if existing:
        print("Admin already exists.")
    else:
        admin = User(
            name='Admin',
            email='admin@trek.com',
            password=generate_password_hash('admin123'),
            role='admin',
            is_active=True,
            is_approved=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully.")