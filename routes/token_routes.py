from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Token, CargoType, User
from datetime import datetime, timedelta
import uuid
from flask import abort

token_bp = Blueprint('token', __name__)

# ------------------------
# Utility: Generate Unique Token Serial
# ------------------------
def generate_serial():
    return str(uuid.uuid4())[:8].upper()  # e.g. 'A8F5B3D9'

# ------------------------
# Company: Dashboard View
# ------------------------
@token_bp.route('/company_dashboard')
@login_required
def company_dashboard():
    if current_user.role != 'company':
        flash("Access denied.", "danger")
        return redirect(url_for('checkpoint.dashboard'))

    recent_tokens = Token.query.filter_by(company_id=current_user.id).order_by(Token.created_at.desc()).limit(5).all()
    total_tokens = Token.query.filter_by(company_id=current_user.id).count()
    total_spent = db.session.query(db.func.sum(Token.price)).filter_by(company_id=current_user.id).scalar() or 0

    return render_template("company_dashboard.html", user=current_user,
                           recent_tokens=recent_tokens,
                           total_tokens=total_tokens,
                           total_spent=total_spent)

# ------------------------
# Company: Purchase Token
# ------------------------
@token_bp.route('/purchase_token', methods=['GET', 'POST'])
@login_required
def purchase_token():
    if current_user.role != 'company':
        flash("Only company users can purchase tokens.", "danger")
        return redirect(url_for('checkpoint.dashboard'))

    cargo_types = CargoType.query.order_by(CargoType.name).all()

    if request.method == 'POST':
        vehicle_plate = request.form['vehicle_plate'].strip().upper()
        cargo_type_id = request.form['cargo_type']
        days_valid = int(request.form.get('valid_days', 3))

        cargo = CargoType.query.get(cargo_type_id)
        if not cargo:
            flash("Invalid cargo type selected.", "danger")
            return redirect(url_for('token.purchase_token'))

        serial = generate_serial()
        expiration = datetime.utcnow() + timedelta(days=days_valid)

        token = Token(
            serial=serial,
            vehicle_plate=vehicle_plate,
            cargo_type_id=cargo.id,
            price=cargo.price,
            expiration_date=expiration,
            company_id=current_user.id
        )
        db.session.add(token)
        db.session.commit()
        flash(f"Token {serial} purchased for ZMW {cargo.price:.2f}", "success")
        return redirect(url_for('token.token_history'))

    return render_template('purchase_token.html', cargo_types=cargo_types)

# ------------------------
# Company: Token History
# ------------------------
@token_bp.route('/token_history')
@login_required
def token_history():
    if current_user.role != 'company':
        return render_template('access_denied.html'), 403

    tokens = Token.query.filter_by(company_id=current_user.id).order_by(Token.created_at.desc()).all()
    return render_template('token_history.html', tokens=tokens)

# ------------------------
# Officer: Verify Token
# ------------------------
@token_bp.route('/verify_token', methods=['GET', 'POST'])
@login_required
def verify_token():
    if current_user.role != 'officer':
        flash("Only checkpoint officers can verify tokens.", "danger")
        return redirect(url_for('checkpoint.entry'))

    status = None
    token = None

    if request.method == 'POST':
        serial = request.form['serial'].strip().upper()
        plate = request.form['vehicle_plate'].strip().upper()

        token = Token.query.filter_by(serial=serial).first()
        if not token:
            status = "invalid"
        elif token.vehicle_plate != plate:
            status = "mismatch"
        elif token.status == 'used':
            status = "used"
        elif token.expiration_date < datetime.utcnow():
            token.status = 'expired'
            db.session.commit()
            status = "expired"
        else:
            token.status = 'used'
            token.used_at = datetime.utcnow()
            db.session.commit()
            status = "valid"

    return render_template('verify_token.html', status=status, token=token)

# ------------------------
# Admin: Manage Cargo Prices
# ------------------------
@token_bp.route('/cargo_prices', methods=['GET', 'POST'])
@login_required
def manage_prices():
    if current_user.role != 'admin':
        flash("Only admins can manage cargo prices.", "danger")
        return redirect(url_for('checkpoint.dashboard'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        price = float(request.form['price'])

        existing = CargoType.query.filter_by(name=name).first()
        if existing:
            flash("Cargo type already exists.", "warning")
        else:
            db.session.add(CargoType(name=name, price=price))
            db.session.commit()
            flash(f"Cargo type '{name}' added with price ZMW {price:.2f}", "success")

    cargo_types = CargoType.query.order_by(CargoType.name).all()
    return render_template('manage_prices.html', cargo_types=cargo_types)


# ------------------------
# Admin: Manage Cargo Types
# ------------------------
@token_bp.route('/manage_cargo', methods=['GET', 'POST'])
@login_required
def manage_cargo():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        name = request.form['name'].strip()
        price = float(request.form['price'])

        if CargoType.query.filter_by(name=name).first():
            flash('Cargo type already exists.', 'warning')
        else:
            new_type = CargoType(name=name, price=price)
            db.session.add(new_type)
            db.session.commit()
            flash(f'Cargo type "{name}" added successfully.', 'success')

    cargos = CargoType.query.order_by(CargoType.name).all()
    return render_template('manage_cargo.html', cargos=cargos)

# ------------------------
# Admin: Update Cargo Price
# ------------------------
@token_bp.route('/update_cargo/<int:id>', methods=['POST'])
@login_required
def update_cargo(id):
    if current_user.role != 'admin':
        abort(403)

    cargo = CargoType.query.get_or_404(id)
    try:
        cargo.price = float(request.form['price'])
        db.session.commit()
        flash('Cargo price updated successfully.', 'success')
    except:
        flash('Invalid price value.', 'danger')

    return redirect(url_for('token.manage_cargo'))

# ------------------------
# Admin: Delete Cargo Type
# ------------------------
@token_bp.route('/delete_cargo/<int:id>', methods=['POST'])
@login_required
def delete_cargo(id):
    if current_user.role != 'admin':
        abort(403)

    cargo = CargoType.query.get_or_404(id)
    db.session.delete(cargo)
    db.session.commit()
    flash('Cargo type deleted.', 'info')

    return redirect(url_for('token.manage_cargo'))

