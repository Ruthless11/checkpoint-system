from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import uuid

db = SQLAlchemy()

# ---------------------
# User model (extended)
# ---------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'company', 'officer'
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_logged_in = db.Column(db.Boolean, default=False)

    # One-to-one relationships (nullable=True allows flexibility)
    company_profile = db.relationship("CompanyProfile", backref="user", uselist=False)
    officer_profile = db.relationship("OfficerProfile", backref="user", uselist=False)
#-------------------
#Officer Profile
#---------------------

class OfficerProfile(db.Model):
    __tablename__ = 'officer_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    nrc = db.Column(db.String(50), unique=True)
    checkpoint = db.Column(db.String(100))  # optional extra

#-------------------
#Company Profile
#---------------------
class CompanyProfile(db.Model):
    __tablename__ = 'company_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    company_name = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    nrc = db.Column(db.String(50), unique=True)


# ---------------------
# Cargo Type & Price
# ---------------------
class CargoType(db.Model):
    __tablename__ = 'cargo_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<CargoType {self.name} @ ZMW {self.price}>"

# ---------------------
# Token Table
# ---------------------
class Token(db.Model):
    __tablename__ = 'tokens'
    id = db.Column(db.Integer, primary_key=True)
    serial = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_plate = db.Column(db.String(20), nullable=False)
    cargo_type_id = db.Column(db.Integer, db.ForeignKey('cargo_types.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, used, expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiration_date = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    cargo_type = db.relationship('CargoType', backref='tokens')

    def is_valid(self):
        now = datetime.utcnow()
        if self.status != 'active':
            return False
        if self.expiration_date < now:
            return False
        return True

# ---------------------
# Vehicle Logs (existing model, now related to tokens)
# ---------------------
class VehicleLog(db.Model):
    __tablename__ = 'vehicle_logs'
    id = db.Column(db.Integer, primary_key=True)
    number_plate = db.Column(db.String(20), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    company = db.relationship('User', foreign_keys=[company_id])
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    location = db.Column(db.String(100))
    checkpoint = db.Column(db.String(50))
    amount_paid = db.Column(db.Float)
    officer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    officer = db.relationship('User', foreign_keys=[officer_id])
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    token_serial = db.Column(db.String(20), db.ForeignKey('tokens.serial'), nullable=True)
    token = db.relationship('Token', backref='vehicle_logs')

# ---------------------
# OfficerShift Model(store shift records per officers)
# ---------------------
class OfficerShift(db.Model):
    __tablename__ = 'officer_shifts'
    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    checkpoint = db.Column(db.String(100), nullable=False)

    officer = db.relationship('User', backref='shifts')
