from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, CompanyProfile, OfficerProfile
from forms import RegisterForm, LoginForm, ChangePasswordForm
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

# ------------------------
# LOGIN ROUTE
# ------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        phone = form.phone.data.strip()
        password = form.password.data
        user = User.query.filter_by(phone=phone).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            user.last_login = datetime.utcnow()
            user.is_logged_in = True
            db.session.commit()

            # Custom welcome message
            if user.role == "company" and user.company_profile:
                flash(f"Welcome {user.company_profile.company_name}!", "success")
            elif user.role == "officer" and user.officer_profile:
                flash(f"Welcome {user.officer_profile.full_name}!", "success")
            else:
                flash(f"Welcome!", "success")

            return redirect_user_based_on_role()
        else:
            flash("Invalid credentials.", "danger")

    return render_template("login.html", form=form)

# ------------------------
# LOGOUT ROUTE
# ------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    current_user.is_logged_in = False
    current_user.last_login = datetime.utcnow()
    db.session.commit()
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

# ------------------------
# REGISTRATION ROUTE (for companies)
# ------------------------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        full_name = form.full_name.data.strip()
        phone = form.phone.data.strip()
        email = form.email.data.strip()
        password = form.password.data
        company_name = form.company_name.data.strip()
        captcha = form.captcha.data.strip()

        if captcha != '8':
            flash("Incorrect CAPTCHA. Try again.", "danger")
            return render_template('register.html', form=form)

        if CompanyProfile.query.filter_by(company_name=company_name).first():
            flash("Company name already exists.", "danger")
            return render_template('register.html', form=form)

        if User.query.filter_by(phone=phone).first():
            flash("Phone number already registered.", "danger")
            return render_template('register.html', form=form)

        new_user = User(
            phone=phone,
            email=email,
            password_hash=generate_password_hash(password),
            role='company', # 👈 Hardcoded since only companies register here
            created_at=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.flush()  # Allows us to get new_user.id

        company_profile = CompanyProfile(
            user_id=new_user.id,
            full_name=full_name,
            company_name=company_name,
            nrc=nrc
        )
        db.session.add(company_profile)
        db.session.commit()

        flash("Registration successful. You can now login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)

# ------------------------
# REDIRECT BASED ON ROLE
# ------------------------
def redirect_user_based_on_role():
    if current_user.role == 'admin':
        return redirect(url_for('checkpoint.dashboard'))
    elif current_user.role == 'officer':
        return redirect(url_for('checkpoint.entry'))
    elif current_user.role == 'company':
        return redirect(url_for('token.company_dashboard'))
    else:
        return render_template("access_denied.html", message="Access denied: Unknown user role.")

# ------------------------
# ADMIN: ADD USER (Officers/Admins)
# ------------------------
@auth_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('Access denied: Only admins can add users.', 'danger')
        return redirect(url_for('checkpoint.dashboard'))

    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        password = request.form['password']
        role = request.form['role'].strip().lower()
        nrc = request.form['nrc'].strip()
        phone = request.form['phone'].strip()
        email = request.form['email'].strip()

        if role not in ['officer', 'admin']:
            flash('Only officers and admins can be added.', 'danger')
            return redirect(url_for('auth.add_user'))

        if User.query.filter_by(phone=phone).first():
            flash('Phone number already exists.', 'danger')
            return redirect(url_for('auth.add_user'))

        if role == 'officer' and OfficerProfile.query.filter_by(nrc=nrc).first():
            flash('NRC already exists for an officer.', 'danger')
            return redirect(url_for('auth.add_user'))

        new_user = User(
            phone=phone,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            created_at=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.flush()

        if role == 'officer':
            officer_profile = OfficerProfile(
                user_id=new_user.id,
                full_name=full_name,
                nrc=nrc
            )
            db.session.add(officer_profile)

        db.session.commit()
        flash(f"{role.capitalize()} added successfully.", "success")

    return render_template('add_user.html')


# ------------------------
# PROFILE PAGE
# ------------------------
@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

# ------------------------
# CHANGE PASSWORD
# ------------------------
@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for('auth.profile'))
        else:
            flash("Incorrect current password.", "danger")
    return render_template('change_password.html', form=form)
