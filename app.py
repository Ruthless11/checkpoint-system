from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from datetime import datetime
from flask_migrate import Migrate
from models import db, User, OfficerProfile
from routes.auth_routes import auth_bp
from routes.checkpoint_routes import checkpoint_bp
from routes.token_routes import token_bp
from routes.admin_routes import admin_bp

# ---- Flask App Setup ----
app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:TrapGres1234@localhost/checkpoint_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
app.config['SECRET_KEY'] = 'your_secret_key'

# ---- Extensions Initialization ----
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

# ---- User Loader ----
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- Register Blueprints ----
app.register_blueprint(auth_bp)
app.register_blueprint(checkpoint_bp)
app.register_blueprint(token_bp, url_prefix='/token')
app.register_blueprint(admin_bp, url_prefix='/admin')

# ---- Create Tables and Default Admin ----
with app.app_context():
    db.create_all()

    # Only create admin if not exists
    existing_admin = User.query.filter_by(phone='0973939888', role='admin').first()
    if not existing_admin:
        # Create the base User entry
        admin_user = User(
            #username='admin',
            phone='0973939888',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            created_at=datetime.utcnow(),
            is_logged_in=False
        )
        db.session.add(admin_user)
        db.session.commit()
        print("✅ Admin user created.")

# ---- Run the App ----
if __name__ == '__main__':
    app.run(debug=True)
