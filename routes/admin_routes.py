from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, CargoType, VehicleLog, User
from sqlalchemy import func 
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from collections import defaultdict
from models import OfficerProfile


admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/cargo_types')
@login_required
def list_cargo_types():
    if current_user.role != 'admin':
        return render_template('access_denied.html'), 403

    cargo_types = CargoType.query.all()
    return render_template('admin/cargo_types.html', cargo_types=cargo_types)


@admin_bp.route('/admin/cargo_types/add', methods=['GET', 'POST'])
@login_required
def add_cargo_type():
    if current_user.role != 'admin':
        return render_template('access_denied.html'), 403

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])

        existing = CargoType.query.filter_by(name=name).first()
        if existing:
            flash('Cargo type already exists.', 'warning')
            return redirect(url_for('admin.list_cargo_types'))

        new_type = CargoType(name=name, price=price)
        db.session.add(new_type)
        db.session.commit()
        flash('Cargo type added.', 'success')
        return redirect(url_for('admin.list_cargo_types'))

    return render_template('admin/add_cargo_type.html')


@admin_bp.route('/admin/cargo_types/edit/<int:type_id>', methods=['GET', 'POST'])
@login_required
def edit_cargo_type(type_id):
    if current_user.role != 'admin':
        return render_template('access_denied.html'), 403

    cargo = CargoType.query.get_or_404(type_id)
    if request.method == 'POST':
        cargo.name = request.form['name']
        cargo.price = float(request.form['price'])
        db.session.commit()
        flash('Cargo type updated.', 'success')
        return redirect(url_for('admin.list_cargo_types'))

    return render_template('admin/edit_cargo_type.html', cargo=cargo)


@admin_bp.route('/admin/cargo_types/delete/<int:type_id>')
@login_required
def delete_cargo_type(type_id):
    if current_user.role != 'admin':
        return render_template('access_denied.html'), 403

    cargo = CargoType.query.get_or_404(type_id)
    db.session.delete(cargo)
    db.session.commit()
    flash('Cargo type deleted.', 'info')
    return redirect(url_for('admin.list_cargo_types'))


@admin_bp.route('/officer_performance', methods=['GET', 'POST'])
@login_required
def officer_performance():
    if current_user.role != 'admin':
        return render_template('access_denied.html', message="Admins only")

    officers = (
        db.session.query(User)
        .join(OfficerProfile)
        .filter(User.role == 'officer')
        .all()
    )

    selected_officer = request.form.get('officer') if request.method == 'POST' else None
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    query = (
        db.session.query(
            OfficerProfile.full_name,
            func.date(VehicleLog.timestamp).label('log_date'),
            func.sum(VehicleLog.amount_paid).label('total_collected')
        )
        .join(User, VehicleLog.officer_id == User.id)
        .join(OfficerProfile, OfficerProfile.user_id == User.id)
    )

    if selected_officer:
        query = query.filter(User.id == int(selected_officer))
    if start_date:
        query = query.filter(VehicleLog.timestamp >= start_date)
    if end_date:
        query = query.filter(VehicleLog.timestamp <= end_date)

    query = query.group_by(OfficerProfile.full_name, func.date(VehicleLog.timestamp))
    results = query.all()


    # Group totals by officer

    officer_totals = defaultdict(float)
    for full_name, date, total in results:
        officer_totals[full_name] += total

    # Convert to list of tuples for display or export

    grouped_results = [(name, amount) for name, amount in officer_totals.items()]
    
    # Export to Excel
    if 'export_excel' in request.form:
        import pandas as pd
        from io import BytesIO
        from flask import send_file

        df = pd.DataFrame(results, columns=["Officer", "Date", "Amount Collected"])
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='officer_performance.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )


    # Export CSV
    if 'export_csv' in request.form:
        import csv
        from io import StringIO
        from flask import Response

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Officer", "Total Amount Collected (ZMW)"])
        for officer, total in grouped_results:
            writer.writerow([officer, f"{total:.2f}"])

        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers["Content-Disposition"] = "attachment; filename=officer_performance.csv"
        return response

    # Export to PDF
    if 'export_pdf' in request.form:
        from io import BytesIO
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        output = BytesIO()
        c = canvas.Canvas(output, pagesize=A4)
        width, height = A4
        y = height - 50

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Officer Performance Report")
        y -= 30
        c.setFont("Helvetica", 10)

        for full_name, date, total in results:
            c.drawString(50, y, f"{date} - {full_name}: ZMW {total:.2f}")
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

        c.save()
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='officer_performance.pdf',
            mimetype='application/pdf'
        )
    

    return render_template(
        "officer_performance.html",
        officers=officers,
        daily_results=results, # from query.group_by(date)
        grouped_results=grouped_results, # from defaultdict summary
        selected_officer=selected_officer,
        start_date=start_date,
        end_date=end_date
    )
