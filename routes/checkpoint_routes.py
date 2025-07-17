from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from sqlalchemy import extract, func
from models import db, VehicleLog, User, CompanyProfile
import io, os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from datetime import datetime, timedelta
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64

checkpoint_bp = Blueprint('checkpoint', __name__)

# ---------------------
# Generate chart image as base64
# ---------------------
def generate_chart_base64(data_dict, title, chart_type='pie'):
    buf = io.BytesIO()
    plt.figure(figsize=(5, 4))

    if chart_type == 'pie':
        plt.pie(data_dict.values(), labels=data_dict.keys(), autopct='%1.1f%%', startangle=90)
    else:
        plt.bar(data_dict.keys(), data_dict.values(), color='skyblue')
        plt.xticks(rotation=45, ha='right')
        plt.ylabel('ZMW')

    plt.title(title)
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ---------------------
# Admin Dashboard
# ---------------------
@checkpoint_bp.route('/')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return render_template('access_denied.html'), 403

    company_id = request.args.get('company_id', type=int)
    checkpoint = request.args.get('checkpoint')
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    week = request.args.get('week', type=int)
    day = request.args.get('day')
    hour = request.args.get('hour', type=int)
    specific_date = request.args.get('date')

    query = VehicleLog.query

    if company_id:
        query = query.filter(VehicleLog.company_id == company_id)
    if checkpoint:
        query = query.filter(VehicleLog.checkpoint == checkpoint)
    if month:
        query = query.filter(extract('month', VehicleLog.timestamp) == month)
    if year:
        query = query.filter(extract('year', VehicleLog.timestamp) == year)
    if week:
        query = query.filter(func.date_part('week', VehicleLog.timestamp) == week)
    if day:
        query = query.filter(func.to_char(VehicleLog.timestamp, 'Day').ilike(f'%{day.capitalize()}%'))
    if hour is not None:
        query = query.filter(extract('hour', VehicleLog.timestamp) == hour)
    if specific_date:
        try:
            dt = datetime.strptime(specific_date, '%Y-%m-%d').date()
            query = query.filter(func.date(VehicleLog.timestamp) == dt)
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "danger")

    logs = query.order_by(VehicleLog.timestamp.desc()).all()
    total_vehicles = len(logs)
    total_amount = sum(log.amount_paid for log in logs)

    companies = db.session.query(User.id, CompanyProfile.company_name)\
        .join(CompanyProfile, CompanyProfile.user_id == User.id)\
        .order_by(CompanyProfile.company_name).all()

    checkpoints = db.session.query(VehicleLog.checkpoint).distinct().order_by(VehicleLog.checkpoint).all()
    years = db.session.query(extract('year', VehicleLog.timestamp)).distinct().order_by(extract('year', VehicleLog.timestamp)).all()

    recent_threshold = datetime.utcnow() - timedelta(minutes=15)
    active_officers = User.query.filter(
        User.role == 'officer',
        User.last_login != None,
        User.last_login >= recent_threshold
    ).all()

    company_chart = checkpoint_chart = None
    if logs:
        company_totals = {}
        checkpoint_totals = {}

        for log in logs:
            company_name = log.company.company_profile.company_name if log.company and log.company.company_profile else "Unknown"
            company_totals[company_name] = company_totals.get(company_name, 0) + log.amount_paid
            checkpoint_totals[log.checkpoint] = checkpoint_totals.get(log.checkpoint, 0) + log.amount_paid

        company_chart = generate_chart_base64(company_totals, "Revenue Share by Company", chart_type='pie')
        checkpoint_chart = generate_chart_base64(checkpoint_totals, "Revenue by Checkpoint", chart_type='bar')

    return render_template('dashboard.html',
                           logs=logs,
                           total_vehicles=total_vehicles,
                           total_amount=total_amount,
                           filters={"company_id": company_id, "checkpoint": checkpoint, "month": month, "year": year, "week": week, "day": day, "hour": hour, "date": specific_date},
                           companies=companies,
                           checkpoints=[c[0] for c in checkpoints],
                           years=[y[0] for y in years],
                           company_chart=company_chart,
                           checkpoint_chart=checkpoint_chart,
                           active_officers=active_officers)


# ---------------------
# Officer Entry Form
# ---------------------
@checkpoint_bp.route('/entry', methods=['GET', 'POST'])
@login_required
def entry():
    if current_user.role != 'officer':
        return render_template('access_denied.html', message="Only officers can access this page.")

    if request.method == 'POST':
        log = VehicleLog(
            number_plate=request.form['number_plate'],
            company_id=request.form.get('company_id'),  # must be valid user id
            phone=request.form['phone'],
            email=request.form['email'],
            location=request.form['location'],
            checkpoint=request.form['checkpoint'],
            amount_paid=float(request.form['amount_paid']),
            officer_id=current_user.id
        )
        db.session.add(log)
        db.session.commit()
        flash("Vehicle entry recorded successfully.", "success")
        return redirect(url_for('checkpoint.entry'))

    companies = db.session.query(User.id, CompanyProfile.company_name)\
        .join(CompanyProfile, CompanyProfile.user_id == User.id)\
        .order_by(CompanyProfile.company_name).all()

    return render_template('entry.html', companies=companies)


# generate_report and email functions below,
@checkpoint_bp.route('/report_download')
@login_required
def report_download():
    return render_template('report_download.html', user=current_user)


@checkpoint_bp.route('/generate_report')
@login_required
def generate_report():
    if current_user.role != 'admin':
        flash("Only admins can generate reports.", "danger")
        return render_template('access_denied.html'), 403

    format = request.args.get('format')
    send_email = request.args.get('email')
    include_chart = request.args.get('include_chart') == '1'

    company_id = request.args.get('company_id', type=int)
    checkpoint = request.args.get('checkpoint')
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    week = request.args.get('week', type=int)
    day = request.args.get('day')
    hour = request.args.get('hour', type=int)
    specific_date = request.args.get('date')

    query = VehicleLog.query

    if company_id:
        query = query.filter(VehicleLog.company_id == company_id)
    if checkpoint:
        query = query.filter(VehicleLog.checkpoint == checkpoint)
    if month:
        query = query.filter(extract('month', VehicleLog.timestamp) == month)
    if year:
        query = query.filter(extract('year', VehicleLog.timestamp) == year)
    if week:
        query = query.filter(func.date_part('week', VehicleLog.timestamp) == week)
    if day:
        query = query.filter(func.to_char(VehicleLog.timestamp, 'Day').ilike(f'%{day.capitalize()}%'))
    if hour is not None:
        query = query.filter(extract('hour', VehicleLog.timestamp) == hour)
    if specific_date:
        try:
            dt = datetime.strptime(specific_date, '%Y-%m-%d').date()
            query = query.filter(func.date(VehicleLog.timestamp) == dt)
        except ValueError:
            flash("Invalid date format for 'date'. Use YYYY-MM-DD.", "danger")

    logs = query.order_by(VehicleLog.timestamp.desc()).all()

    data = []
    for l in logs:
        company_name = l.company.company_profile.company_name if l.company and l.company.company_profile else "Unknown"
        data.append({
            "Number Plate": l.number_plate,
            "Company": company_name,
            "Checkpoint": l.checkpoint,
            "Amount Paid": l.amount_paid,
            "Timestamp": l.timestamp.strftime('%Y-%m-%d %H:%M')
        })

    if format == 'excel':
        output = io.BytesIO()
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')
            worksheet = writer.sheets['Report']
            workbook = writer.book
            fmt = workbook.add_format({'num_format': 'ZMW #,##0.00', 'align': 'center'})
            worksheet.set_column(0, 4, 20, fmt)
            worksheet.write(len(df) + 1, 2, 'Total:')
            worksheet.write_formula(len(df) + 1, 3, f'=SUM(D2:D{len(df)+1})', fmt)
        output.seek(0)
        if send_email:
            return send_report_email(send_email, output, 'checkpoint_report.xlsx', 'excel')
        return send_file(output, download_name='checkpoint_report.xlsx', as_attachment=True)

    elif format == 'pdf':
        output = io.BytesIO()
        p = canvas.Canvas(output, pagesize=A4)
        width, height = A4
        y = height - 60

        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'logo.png')
        if os.path.exists(logo_path):
            p.drawImage(ImageReader(logo_path), 40, y, width=80, preserveAspectRatio=True, mask='auto')

        p.setFont("Helvetica-Bold", 14)
        p.drawString(140, y, "Checkpoint Report")
        y -= 20
        p.setFont("Helvetica", 9)
        p.drawString(140, y, "Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        y -= 40

        if include_chart and logs:
            chart_io = io.BytesIO()
            df = pd.DataFrame(data)
            df_grouped = df.groupby("Company")["Amount Paid"].sum()
            plt.figure(figsize=(5, 4))
            df_grouped.plot.pie(autopct='%1.1f%%')
            plt.title("Revenue Share by Company")
            plt.ylabel("")
            plt.tight_layout()
            plt.savefig(chart_io, format='png')
            plt.close()
            chart_io.seek(0)
            p.drawImage(ImageReader(chart_io), 100, y - 200, width=400, height=200)
            y -= 220

        headers = ["Plate", "Company", "Checkpoint", "Amount", "Time"]
        p.setFont("Helvetica-Bold", 10)
        for i, h in enumerate(headers):
            p.drawString(40 + i * 100, y, h)
        y -= 20

        total = 0
        p.setFont("Helvetica", 9)
        for d in data:
            p.drawString(40, y, d["Number Plate"])
            p.drawString(140, y, d["Company"][:15])
            p.drawString(240, y, d["Checkpoint"][:12])
            p.drawString(340, y, f"ZMW {d['Amount Paid']:.2f}")
            p.drawString(440, y, d["Timestamp"])
            total += d['Amount Paid']
            y -= 18
            if y < 60:
                p.showPage()
                y = height - 60

        p.setFont("Helvetica-Bold", 10)
        p.drawString(40, y - 10, f"Total Revenue: ZMW {total:,.2f}")
        p.setFont("Helvetica-Oblique", 8)
        p.drawString(40, 30, "Generated by Vehicle Checkpoint Monitoring System")
        p.save()
        output.seek(0)

        if send_email:
            return send_report_email(send_email, output, 'checkpoint_report.pdf', 'pdf')
        return send_file(output, download_name='checkpoint_report.pdf', as_attachment=True)

    return render_template('report_download.html', user=current_user)

