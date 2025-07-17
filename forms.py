# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional


class RegisterForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    company_name = StringField('Company Name', validators=[DataRequired()])
    nrc = StringField('NRC', validators=[Optional()])
    captcha = StringField('CAPTCHA: 5 + 3 = ?', validators=[DataRequired()])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    phone = StringField('Phone Number', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


from wtforms import PasswordField
from wtforms.validators import EqualTo

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')
