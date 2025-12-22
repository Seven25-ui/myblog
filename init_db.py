from app import db, app, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    # Auto-create admin if not exists
    if not User.query.filter_by(username="admin").first():
        admin_user = User(username="admin", password=generate_password_hash("admin123"))
        db.session.add(admin_user)
        db.session.commit()
        print("Admin created: username=admin, password=admin123")
    print("All tables created successfully.")
