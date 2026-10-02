import os
import csv
import calendar
import io
import hmac
import secrets
import threading
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response, abort, g, current_app
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config, startup_warnings

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)


def Choice(*values):
    """A column restricted to a fixed set of strings.

    Stored as VARCHAR plus a CHECK constraint rather than a native PostgreSQL
    ENUM type. A native enum is a separate database object that needs a unique
    name per column and an ALTER TYPE migration to add a value; the VARCHAR +
    CHECK form behaves the same for the app, is created by db.create_all()
    without extra steps, and is trivial to extend.
    """
    return db.Enum(
        *values,
        native_enum=False,
        create_constraint=True,
        length=max(len(v) for v in values),
    )

# ==========================================
# DATABASE MODELS
# ==========================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(Choice('admin', 'health_worker', 'supervisor'), nullable=False, default='health_worker')
    phone = db.Column(db.String(15), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Household(db.Model):
    __tablename__ = 'households'
    id = db.Column(db.Integer, primary_key=True)
    household_number = db.Column(db.String(50), unique=True, nullable=False)
    head_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    area = db.Column(db.String(100), nullable=False)
    ward = db.Column(db.String(50), nullable=False)
    contact_no = db.Column(db.String(15), nullable=True)
    economic_status = db.Column(Choice('APL', 'BPL', 'AAY'), default='BPL')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    beneficiaries = db.relationship('Beneficiary', backref='household', lazy=True, cascade="all, delete-orphan")
    visits = db.relationship('HomeVisit', backref='household', lazy=True, cascade="all, delete-orphan")


class Beneficiary(db.Model):
    __tablename__ = 'beneficiaries'
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('households.id', ondelete='CASCADE'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(Choice('Male', 'Female', 'Other'), nullable=False)
    health_id = db.Column(db.String(50), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=True)
    blood_group = db.Column(Choice('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'), nullable=True)
    is_disabled = db.Column(db.Boolean, default=False)
    disability_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessments = db.relationship('HealthAssessment', backref='beneficiary', lazy=True, cascade="all, delete-orphan")
    maternal_records = db.relationship('MaternalRecord', backref='beneficiary', lazy=True, cascade="all, delete-orphan")
    immunizations = db.relationship('ImmunizationSchedule', backref='beneficiary', lazy=True, cascade="all, delete-orphan")
    prescriptions = db.relationship('Prescription', backref='beneficiary', lazy=True, cascade="all, delete-orphan")
    referrals = db.relationship('Referral', backref='beneficiary', lazy=True, cascade="all, delete-orphan")

    @property
    def age(self):
        if self.dob:
            today = date.today()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return 0


class HealthAssessment(db.Model):
    __tablename__ = 'health_assessments'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    chw_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assessment_date = db.Column(db.Date, default=date.today)
    weight = db.Column(db.Float, nullable=True)  # in kg
    height = db.Column(db.Float, nullable=True)  # in cm
    bmi = db.Column(db.Float, nullable=True)
    bp_systolic = db.Column(db.Integer, nullable=True)
    bp_diastolic = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, nullable=True)  # Fahrenheit
    hemoglobin = db.Column(db.Float, nullable=True)   # g/dL
    blood_sugar = db.Column(db.Float, nullable=True)  # mg/dL
    symptoms = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chw = db.relationship('User', backref='assessments')


class MaternalRecord(db.Model):
    __tablename__ = 'maternal_records'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    lmp_date = db.Column(db.Date, nullable=False)
    edd_date = db.Column(db.Date, nullable=False)
    anc_visits_count = db.Column(db.Integer, default=0)
    pnc_visits_count = db.Column(db.Integer, default=0)
    hemoglobin = db.Column(db.Float, nullable=True)
    blood_pressure = db.Column(db.String(20), nullable=True)
    is_high_risk = db.Column(db.Boolean, default=False)
    high_risk_reason = db.Column(db.Text, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    delivery_type = db.Column(Choice('Normal', 'Cesarean', 'Assisted'), nullable=True)
    delivery_place = db.Column(db.String(200), nullable=True)
    baby_weight = db.Column(db.Float, nullable=True)
    status = db.Column(Choice('Pregnant', 'Delivered', 'Postnatal', 'Closed'), default='Pregnant')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChildRecord(db.Model):
    __tablename__ = 'child_records'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    mother_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='SET NULL'), nullable=True)
    birth_weight = db.Column(db.Float, nullable=True)
    birth_date = db.Column(db.Date, nullable=False)
    immunization_status = db.Column(Choice('Pending', 'Partial', 'Complete'), default='Pending')
    growth_category = db.Column(Choice('Normal', 'Underweight', 'Severely Underweight', 'Overweight'), default='Normal')
    feeding_type = db.Column(Choice('Breastfed', 'Formula', 'Mixed'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # The backref needs an ORM cascade as well as the DB-level ON DELETE CASCADE.
    # Without it SQLAlchemy tries to UPDATE child_records.beneficiary_id to NULL
    # before deleting, which PostgreSQL rejects (NOT NULL) while SQLite accepts it.
    beneficiary = db.relationship(
        'Beneficiary',
        foreign_keys=[beneficiary_id],
        backref=db.backref('child_profile', cascade="all, delete-orphan", passive_deletes=True),
    )
    mother = db.relationship('Beneficiary', foreign_keys=[mother_id], passive_deletes=True)


class Vaccine(db.Model):
    __tablename__ = 'vaccines'
    id = db.Column(db.Integer, primary_key=True)
    vaccine_name = db.Column(db.String(100), nullable=False)
    target_age_months = db.Column(db.Integer, nullable=False)
    dose_number = db.Column(db.Integer, default=1)
    description = db.Column(db.Text, nullable=True)


# India's full routine immunisation schedule, as one row per dose. Kept as a
# constant rather than seeded once so the scheduler always has a schedule to
# work from even on a database that has never been seeded.
NATIONAL_IMMUNISATION_SCHEDULE = [
    ('BCG',                     0,   1, 'Tuberculosis vaccine, given at birth'),
    ('Hepatitis B Birth Dose',  0,   1, 'Hepatitis B, within 24 hours of birth'),
    ('OPV 0',                   0,   1, 'Oral Polio Vaccine, at birth'),
    ('OPV 1',                   2,   1, 'Oral Polio Vaccine, first dose'),
    ('Rotavirus 1',             2,   1, 'Rotavirus diarrhoea vaccine, first dose'),
    ('Pentavalent 1',           2,   1, 'DPT + Hepatitis B + Hib, first dose'),
    ('OPV 2',                   4,   2, 'Oral Polio Vaccine, second dose'),
    ('Rotavirus 2',             4,   2, 'Rotavirus diarrhoea vaccine, second dose'),
    ('Pentavalent 2',           4,   2, 'DPT + Hepatitis B + Hib, second dose'),
    ('Pentavalent 3',           6,   3, 'DPT + Hepatitis B + Hib, third dose'),
    ('OPV 3',                   6,   3, 'Oral Polio Vaccine, third dose'),
    ('Measles / Rubella 1',     9,   1, 'MR, first dose'),
    ('DPT Booster 1',           16,  1, 'Diphtheria, Pertussis, Tetanus booster'),
    ('Measles / Rubella 2',     18,  2, 'MR, second dose'),
    ('Td',                      120, 1, 'Tetanus-diphtheria, at 10 years'),
    ('Td (16 yr)',              192, 1, 'Tetanus-diphtheria, at 16 years'),
]


def add_months(start, months):
    """Add whole months to a date, clamping the day to the target month.

    Adding 6 months to 31 Aug would otherwise land on 28 Feb the following year;
    clamping keeps the dose due on the last day of the month instead of
    spilling backwards into the previous one.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return start.replace(year=year, month=month, day=min(start.day, last_day))


def ensure_vaccines():
    """Load the vaccine master list if the table is empty.

    Returns a list ordered by due age. This deliberately does NOT key the result
    by target_age_months: the real schedule has several distinct vaccines due at
    the same age (five at 6 weeks alone — OPV-1, DPT-1, Hep B, Hib, Rotavirus),
    so a dict would silently drop all but the last of each group. A list keeps
    every dose the master list defines.
    """
    vaccines = Vaccine.query.all()
    if not vaccines:
        vaccines = [
            Vaccine(vaccine_name=name, target_age_months=months,
                    dose_number=dose, description=description)
            for name, months, dose, description in NATIONAL_IMMUNISATION_SCHEDULE
        ]
        db.session.add_all(vaccines)
        db.session.commit()
    return sorted(vaccines, key=lambda v: (v.target_age_months, v.dose_number))


def child_due_vaccines(vaccines, child_record):
    """The subset of the master list that applies to a child.

    Vaccines with a negative target age are pregnancy doses (Tetanus Toxoid
    given to the mother), not childhood immunisations, and their due date is
    worked out from the mother's LMP rather than the child's birth. Including
    them here would place a dose due before the child was born.
    """
    return [v for v in vaccines if v.target_age_months >= 0]


def generate_schedule_for(child_record, vaccines):
    """Queue every vaccine dose a child is due, from their birth date.

    Only doses that are not already on file are created, so running this again
    for the same child adds nothing. A dose whose due date has passed is filed
    as Overdue rather than Pending.
    """
    already = {
        s.vaccine_id for s in ImmunizationSchedule.query.filter_by(
            beneficiary_id=child_record.beneficiary_id).all()
    }
    today = date.today()
    created = 0

    for vaccine in child_due_vaccines(vaccines, child_record):
        if vaccine.id in already:
            continue
        due = add_months(child_record.birth_date, vaccine.target_age_months)
        db.session.add(ImmunizationSchedule(
            beneficiary_id=child_record.beneficiary_id,
            vaccine_id=vaccine.id,
            scheduled_date=due,
            status='Overdue' if due < today else 'Pending',
        ))
        created += 1

    return created


class ImmunizationSchedule(db.Model):
    __tablename__ = 'immunization_schedules'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    given_date = db.Column(db.Date, nullable=True)
    status = db.Column(Choice('Pending', 'Completed', 'Missed', 'Overdue'), default='Pending')
    administered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    vaccine = db.relationship('Vaccine')
    worker = db.relationship('User')

    @property
    def display_status(self):
        """The status to show, which is not always the stored one.

        A dose stays 'Pending' in the database until somebody acts on it, but a
        Pending dose whose date has already gone by is overdue in the field. The
        rule is applied here rather than by rewriting rows on page load, so that
        simply looking at the list never modifies the database.
        """
        if self.status == 'Pending' and self.scheduled_date < date.today():
            return 'Overdue'
        return self.status


class Medicine(db.Model):
    __tablename__ = 'medicines'
    id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50), default='Tablets')
    expiry_date = db.Column(db.Date, nullable=True)
    reorder_level = db.Column(db.Integer, default=10)


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    prescribed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    prescribed_date = db.Column(db.Date, default=date.today)
    dosage = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    quantity_dispensed = db.Column(db.Integer, default=0)
    status = db.Column(Choice('Active', 'Completed', 'Discontinued'), default='Active')

    medicine = db.relationship('Medicine')
    prescriber = db.relationship('User')


class HomeVisit(db.Model):
    __tablename__ = 'home_visits'
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('households.id', ondelete='CASCADE'), nullable=False)
    chw_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    visit_date = db.Column(db.Date, nullable=False)
    purpose = db.Column(db.Text, nullable=False)
    observations = db.Column(db.Text, nullable=True)
    followup_date = db.Column(db.Date, nullable=True)
    followup_notes = db.Column(db.Text, nullable=True)
    status = db.Column(Choice('Scheduled', 'Completed', 'Cancelled', 'Follow-up Required'), default='Scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chw = db.relationship('User')


class Referral(db.Model):
    __tablename__ = 'referrals'
    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('beneficiaries.id', ondelete='CASCADE'), nullable=False)
    referred_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    referral_date = db.Column(db.Date, default=date.today)
    reason = db.Column(db.Text, nullable=False)
    hospital_name = db.Column(db.String(200), nullable=False)
    priority = db.Column(Choice('Low', 'Medium', 'High', 'Emergency'), default='Medium')
    status = db.Column(Choice('Pending', 'Accepted', 'Completed', 'Cancelled'), default='Pending')
    outcome = db.Column(db.Text, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referrer = db.relationship('User')


# ==========================================
# AUTHENTICATION & AUTHORIZATION
# ==========================================

ROLE_LABELS = {
    'admin': 'System Administrator',
    'health_worker': 'Community Health Worker',
    'supervisor': 'Medical Supervisor',
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Restrict a view to the given roles. Admins always pass.

    Any authenticated user is allowed to read (GET); only writes are
    restricted, so a CHW can browse the whole system but cannot perform
    an action reserved for another role.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))

            user_role = session.get('role')
            if user_role == 'admin':
                return f(*args, **kwargs)

            # Reads are open to every signed-in role.
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return f(*args, **kwargs)

            if user_role not in roles:
                flash(
                    f'Your role ({ROLE_LABELS.get(user_role, user_role)}) '
                    f'is not permitted to perform this action.',
                    'danger'
                )
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Restrict a view to administrators, for reads as well as writes.

    role_required() deliberately lets every role read a module so a CHW can
    browse the whole system. The admin area is the exception: nobody but an
    admin may load these pages at all.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))

        if session.get('role') != 'admin':
            flash('This area is restricted to System Administrators.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# CSRF PROTECTION
# ==========================================

def generate_csrf_token():
    """Return this session's CSRF token, creating it on first use."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


app.jinja_env.globals['csrf_token'] = generate_csrf_token
app.jinja_env.globals['role_labels'] = ROLE_LABELS


@app.before_request
def enforce_csrf():
    """Reject state-changing requests that do not carry a valid token."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return

    if request.endpoint == 'static':
        return

    sent = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    expected = session.get('_csrf_token')

    if not expected or not sent or not hmac.compare_digest(str(sent), str(expected)):
        db.session.rollback()
        flash('Your session expired or the form was tampered with. Please try again.', 'danger')
        return abort(403)


# ==========================================
# SCHEMA BOOTSTRAP (serverless-friendly)
# ==========================================
#
# On Vercel there is no "python app.py" step and no shell on the server, so the
# app creates its own tables the first time a function instance handles a
# request. create_all() only creates tables that are missing, so this is safe
# to run against a database that already has data. A Postgres advisory lock
# makes simultaneous cold starts take turns instead of racing each other.

_schema_lock = threading.Lock()
_schema_ready = False
_SCHEMA_ADVISORY_LOCK_ID = 727274


def _bootstrap_admin():
    """Create the first admin from environment variables, if none exists.

    A fresh database has no accounts, and self-registration can only create
    health workers, so without this nobody could ever sign in as an admin.
    Set BOOTSTRAP_ADMIN_PASSWORD (and optionally BOOTSTRAP_ADMIN_USERNAME) in
    the hosting dashboard; remove them once you have logged in.
    """
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
    if not password:
        return
    if User.query.filter_by(role='admin').first():
        return
    if len(password) < Config.MIN_PASSWORD_LENGTH:
        app.logger.warning(
            'BOOTSTRAP_ADMIN_PASSWORD is shorter than %d characters; no admin was created.',
            Config.MIN_PASSWORD_LENGTH,
        )
        return

    username = (os.environ.get('BOOTSTRAP_ADMIN_USERNAME') or 'admin').strip()
    if User.query.filter_by(username=username).first():
        app.logger.warning(
            "BOOTSTRAP_ADMIN: a user named %r already exists and is not an admin; "
            "no admin was created.", username)
        return

    admin = User(username=username, full_name='System Administrator', role='admin')
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    app.logger.info('Bootstrap admin %r created.', username)


def ensure_schema():
    """Create missing tables (and the bootstrap admin) once per process."""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        with db.engine.begin() as conn:
            if conn.dialect.name == 'postgresql':
                conn.execute(text('SELECT pg_advisory_xact_lock(:id)'), {'id': _SCHEMA_ADVISORY_LOCK_ID})
            db.metadata.create_all(conn)
        try:
            _bootstrap_admin()
        except Exception:
            db.session.rollback()
            app.logger.exception('Bootstrap admin creation failed.')
        _schema_ready = True


@app.before_request
def prepare_database():
    """Make sure the tables exist before any view touches the database."""
    if _schema_ready or request.endpoint == 'static':
        return
    try:
        ensure_schema()
    except Exception:
        # Leave _schema_ready False so the next request tries again, and let
        # this one carry on: pages that need the database will show the 500
        # page, and the real cause is in the function logs.
        db.session.rollback()
        app.logger.exception('Could not prepare the database schema.')


# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Same reason as /register: the login template lives in the login_content
    # block, which a signed-in session never reaches.
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'danger')
                return render_template('login.html')

            session['user_id'] = user.id
            session['username'] = user.username
            session['full_name'] = user.full_name
            session['role'] = user.role
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    # register.html renders into the login_content block, which base.html only
    # shows to logged-out visitors. Without this guard a signed-in user would be
    # served a blank page with no form, and their POST would fail the CSRF check.
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        full_name = (request.form.get('full_name') or '').strip()
        password = request.form.get('password') or ''
        phone = (request.form.get('phone') or '').strip()

        # Self-registration may never mint an admin or supervisor: the role
        # is chosen at signup only by an existing admin from /admin/users.
        role = 'health_worker'

        min_len = current_app.config.get('MIN_PASSWORD_LENGTH', 8)

        if not username or not full_name or not password:
            flash('All fields marked required must be filled in.', 'danger')
            return render_template('register.html')
        if len(password) < min_len:
            flash(f'Password must be at least {min_len} characters long.', 'danger')
            return render_template('register.html')
        if phone and not phone.isdigit():
            flash('Phone number must contain digits only.', 'danger')
            return render_template('register.html')

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already taken. Please choose another.', 'danger')
            return render_template('register.html')

        user = User(
            username=username,
            full_name=full_name,
            role=role,
            phone=phone
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)


@app.route('/dashboard')
@login_required
def dashboard():
    total_households = Household.query.count()
    total_beneficiaries = Beneficiary.query.count()
    pregnant_count = MaternalRecord.query.filter_by(status='Pregnant').count()
    due_vaccinations = ImmunizationSchedule.query.filter(
        ImmunizationSchedule.status.in_(['Pending', 'Overdue'])
    ).count()
    pending_visits = HomeVisit.query.filter_by(status='Scheduled').count()
    high_risk_referrals = Referral.query.filter(
        Referral.priority.in_(['High', 'Emergency']),
        Referral.status == 'Pending'
    ).count()

    recent_assessments = HealthAssessment.query.order_by(
        HealthAssessment.created_at.desc()
    ).limit(5).all()

    return render_template(
        'dashboard.html',
        total_households=total_households,
        total_beneficiaries=total_beneficiaries,
        pregnant_count=pregnant_count,
        due_vaccinations=due_vaccinations,
        pending_visits=pending_visits,
        high_risk_referrals=high_risk_referrals,
        recent_assessments=recent_assessments
    )


# --- HOUSEHOLD ROUTES ---

@app.route('/households')
@login_required
def households():
    all_households = Household.query.order_by(Household.created_at.desc()).all()
    return render_template('households.html', households=all_households)


@app.route('/households/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_household():
    if request.method == 'POST':
        try:
            household_number = request.form.get('household_number')
            head_name = request.form.get('head_name')
            address = request.form.get('address')
            area = request.form.get('area')
            ward = request.form.get('ward')
            contact_no = request.form.get('contact_no')
            economic_status = request.form.get('economic_status', 'BPL')

            existing = Household.query.filter_by(household_number=household_number).first()
            if existing:
                flash(f'Household number {household_number} already exists.', 'danger')
                return render_template('household_form.html')

            household = Household(
                household_number=household_number,
                head_name=head_name,
                address=address,
                area=area,
                ward=ward,
                contact_no=contact_no,
                economic_status=economic_status
            )
            db.session.add(household)
            db.session.commit()
            flash('Household registered successfully!', 'success')
            return redirect(url_for('households'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering household: {str(e)}', 'danger')

    return render_template('household_form.html', household=None)


@app.route('/households/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def edit_household(id):
    household = Household.query.get_or_404(id)
    if request.method == 'POST':
        try:
            household.head_name = request.form.get('head_name')
            household.address = request.form.get('address')
            household.area = request.form.get('area')
            household.ward = request.form.get('ward')
            household.contact_no = request.form.get('contact_no')
            household.economic_status = request.form.get('economic_status')

            db.session.commit()
            flash('Household updated successfully!', 'success')
            return redirect(url_for('households'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating household: {str(e)}', 'danger')

    return render_template('household_form.html', household=household)


@app.route('/households/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'supervisor')
def delete_household(id):
    household = Household.query.get_or_404(id)
    try:
        member_count = len(household.beneficiaries)
        name = household.household_number
        db.session.delete(household)
        db.session.commit()
        if member_count:
            flash(
                f'Household {name} and its {member_count} beneficiary record(s) were deleted.',
                'success'
            )
        else:
            flash(f'Household {name} deleted successfully!', 'success')
        return redirect(url_for('households'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting household: {str(e)}', 'danger')
        return redirect(url_for('households'))


# --- BENEFICIARY ROUTES ---

@app.route('/beneficiaries')
@login_required
def beneficiaries():
    gender_filter = request.args.get('gender')
    household_filter = request.args.get('household_id')
    search = request.args.get('search')

    query = Beneficiary.query

    if gender_filter:
        query = query.filter_by(gender=gender_filter)
    if household_filter and household_filter.isdigit():
        query = query.filter_by(household_id=int(household_filter))
    if search:
        query = query.filter(
            (Beneficiary.full_name.ilike(f'%{search}%')) |
            (Beneficiary.health_id.ilike(f'%{search}%'))
        )

    all_beneficiaries = query.order_by(Beneficiary.created_at.desc()).all()
    all_households = Household.query.all()
    return render_template('beneficiaries.html', beneficiaries=all_beneficiaries, households=all_households)


@app.route('/beneficiaries/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_beneficiary():
    if request.method == 'POST':
        try:
            household_id = request.form.get('household_id')
            full_name = request.form.get('full_name')
            dob_str = request.form.get('dob')
            gender = request.form.get('gender')
            health_id = request.form.get('health_id')
            mobile = request.form.get('mobile')
            blood_group = request.form.get('blood_group') or None
            is_disabled = True if request.form.get('is_disabled') else False
            disability_details = request.form.get('disability_details')
            continue_to_maternal = bool(request.form.get('register_maternal_now'))

            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()

            existing = Beneficiary.query.filter_by(health_id=health_id).first()
            if existing:
                flash(f'Health ID {health_id} already registered.', 'danger')
                return render_template('beneficiary_form.html', households=Household.query.all())

            beneficiary = Beneficiary(
                household_id=household_id,
                full_name=full_name,
                dob=dob,
                gender=gender,
                health_id=health_id,
                mobile=mobile,
                blood_group=blood_group,
                is_disabled=is_disabled,
                disability_details=disability_details
            )
            db.session.add(beneficiary)
            db.session.commit()
            flash('Beneficiary registered successfully!', 'success')

            # Option A: registering a pregnant woman should not need a second
            # trip to the Maternal module to record the pregnancy.  Hand the
            # new person straight to the maternal form, already selected.
            if continue_to_maternal and gender == 'Female':
                return redirect(url_for('add_maternal', beneficiary_id=beneficiary.id))
            return redirect(url_for('beneficiaries'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering beneficiary: {str(e)}', 'danger')

    all_households = Household.query.all()
    # Generate auto health ID recommendation
    count = Beneficiary.query.count() + 1
    auto_health_id = f"HID-{datetime.now().strftime('%Y')}-{count:04d}"

    return render_template('beneficiary_form.html', households=all_households, auto_health_id=auto_health_id)


@app.route('/beneficiaries/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def edit_beneficiary(id):
    b = Beneficiary.query.get_or_404(id)
    if request.method == 'POST':
        try:
            b.full_name = request.form.get('full_name')
            b.dob = datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date()
            b.gender = request.form.get('gender')
            b.mobile = request.form.get('mobile')
            b.blood_group = request.form.get('blood_group') or None
            b.is_disabled = True if request.form.get('is_disabled') else False
            b.disability_details = request.form.get('disability_details')

            new_household_id = request.form.get('household_id')
            if new_household_id:
                b.household_id = new_household_id

            db.session.commit()
            flash('Beneficiary updated successfully!', 'success')
            return redirect(url_for('beneficiary_detail', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating beneficiary: {str(e)}', 'danger')

    return render_template(
        'beneficiary_form.html',
        households=Household.query.all(),
        beneficiary=b
    )


@app.route('/beneficiaries/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'supervisor')
def delete_beneficiary(id):
    b = Beneficiary.query.get_or_404(id)
    try:
        name = b.full_name
        db.session.delete(b)
        db.session.commit()
        flash(f'Beneficiary {name} and all linked records deleted.', 'success')
        return redirect(url_for('beneficiaries'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting beneficiary: {str(e)}', 'danger')
        return redirect(url_for('beneficiaries'))


@app.route('/beneficiary/<int:id>')
@login_required
def beneficiary_detail(id):
    b = Beneficiary.query.get_or_404(id)
    assessments = HealthAssessment.query.filter_by(beneficiary_id=id).order_by(HealthAssessment.assessment_date.desc()).all()
    maternal_records = MaternalRecord.query.filter_by(beneficiary_id=id).all()
    immunizations = ImmunizationSchedule.query.filter_by(beneficiary_id=id).all()
    prescriptions = Prescription.query.filter_by(beneficiary_id=id).all()
    referrals = Referral.query.filter_by(beneficiary_id=id).all()

    return render_template(
        'beneficiary_detail.html',
        beneficiary=b,
        assessments=assessments,
        maternal_records=maternal_records,
        immunizations=immunizations,
        prescriptions=prescriptions,
        referrals=referrals
    )


# --- HEALTH ASSESSMENT ROUTES ---

@app.route('/assessments')
@login_required
def assessments():
    all_assessments = HealthAssessment.query.order_by(HealthAssessment.assessment_date.desc()).all()
    return render_template('assessments.html', assessments=all_assessments)


@app.route('/assessments/add', methods=['GET', 'POST'])
@login_required
def add_assessment():
    if request.method == 'POST':
        beneficiary_id = request.form.get('beneficiary_id')
        if beneficiary_id:
            return redirect(url_for('add_assessment_for_beneficiary', beneficiary_id=beneficiary_id))
    beneficiaries = Beneficiary.query.order_by(Beneficiary.full_name).all()
    return render_template('assessment_select_beneficiary.html', beneficiaries=beneficiaries)


@app.route('/assessment/new/<int:beneficiary_id>', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_assessment_for_beneficiary(beneficiary_id):
    b = Beneficiary.query.get_or_404(beneficiary_id)
    if request.method == 'POST':
        try:
            assessment_date_str = request.form.get('assessment_date', date.today().strftime('%Y-%m-%d'))
            assessment_date = datetime.strptime(assessment_date_str, '%Y-%m-%d').date()

            weight = float(request.form.get('weight')) if request.form.get('weight') else None
            height = float(request.form.get('height')) if request.form.get('height') else None

            bmi = None
            # A BMI typed into the form wins over the computed one. Some
            # assessments record a measured BMI that deliberately differs from
            # height/weight (amputees, edema, infants measured by length), so
            # silently recomputing would discard the observation. Falls back to
            # the calculation whenever the field is left blank.
            typed_bmi = request.form.get('bmi')
            if typed_bmi:
                try:
                    parsed_bmi = float(typed_bmi)
                    if 1 <= parsed_bmi <= 100:
                        bmi = round(parsed_bmi, 2)
                except ValueError:
                    pass
            if bmi is None and weight and height and height > 0:
                height_m = height / 100.0
                bmi = round(weight / (height_m * height_m), 2)

            bp_systolic = int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None
            bp_diastolic = int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None
            temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
            hemoglobin = float(request.form.get('hemoglobin')) if request.form.get('hemoglobin') else None
            blood_sugar = float(request.form.get('blood_sugar')) if request.form.get('blood_sugar') else None
            symptoms = request.form.get('symptoms')
            notes = request.form.get('notes')

            assessment = HealthAssessment(
                beneficiary_id=beneficiary_id,
                chw_id=session.get('user_id'),
                assessment_date=assessment_date,
                weight=weight,
                height=height,
                bmi=bmi,
                bp_systolic=bp_systolic,
                bp_diastolic=bp_diastolic,
                temperature=temperature,
                hemoglobin=hemoglobin,
                blood_sugar=blood_sugar,
                symptoms=symptoms,
                notes=notes
            )
            db.session.add(assessment)
            db.session.commit()
            flash('Health assessment logged successfully!', 'success')
            return redirect(url_for('beneficiary_detail', id=beneficiary_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error logging health assessment: {str(e)}', 'danger')

    return render_template('assessment_form.html', beneficiary=b)


# --- MATERNAL & CHILD ROUTES ---

@app.route('/maternal')
@login_required
def maternal():
    maternal_records = MaternalRecord.query.order_by(MaternalRecord.created_at.desc()).all()
    child_records = ChildRecord.query.order_by(ChildRecord.created_at.desc()).all()
    return render_template('maternal.html', maternal_records=maternal_records, child_records=child_records)


@app.route('/maternal/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_maternal():
    if request.method == 'POST':
        try:
            beneficiary_id = request.form.get('beneficiary_id')
            lmp_date_str = request.form.get('lmp_date')
            lmp_date = datetime.strptime(lmp_date_str, '%Y-%m-%d').date()

            # EDD calculation: LMP + 280 days
            edd_date = lmp_date + timedelta(days=280)

            hemoglobin = float(request.form.get('hemoglobin')) if request.form.get('hemoglobin') else None
            blood_pressure = request.form.get('blood_pressure')
            is_high_risk = True if request.form.get('is_high_risk') else False
            high_risk_reason = request.form.get('high_risk_reason')

            maternal_record = MaternalRecord(
                beneficiary_id=beneficiary_id,
                lmp_date=lmp_date,
                edd_date=edd_date,
                hemoglobin=hemoglobin,
                blood_pressure=blood_pressure,
                is_high_risk=is_high_risk,
                high_risk_reason=high_risk_reason,
                status='Pregnant'
            )
            db.session.add(maternal_record)
            db.session.commit()
            flash('Maternal pregnancy record created successfully!', 'success')
            return redirect(url_for('maternal'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding maternal record: {str(e)}', 'danger')

    # Pre-select the person being routed here from the beneficiary form, so the
    # CHW does not have to pick them again from a long dropdown.
    preselected = request.args.get('beneficiary_id') or request.form.get('beneficiary_id')
    female_beneficiaries = Beneficiary.query.filter_by(gender='Female').all()
    return render_template('maternal_form.html', female_beneficiaries=female_beneficiaries, preselected_id=preselected)


@app.route('/maternal/add_child', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_child():
    if request.method == 'POST':
        try:
            beneficiary_id = request.form.get('beneficiary_id')
            if not beneficiary_id:
                raise ValueError('Select the child this record belongs to.')

            # One child record per beneficiary. Without this the same child can
            # be registered repeatedly, and every duplicate then produces its
            # own full set of scheduled doses when a schedule is generated,
            # which is how one person ends up filling the immunization list.
            if ChildRecord.query.filter_by(beneficiary_id=beneficiary_id).first():
                flash('That beneficiary already has a child record.', 'danger')
                return redirect(url_for('add_child'))

            child = Beneficiary.query.get_or_404(int(beneficiary_id))
            mother_id = request.form.get('mother_id') or None
            if mother_id and int(mother_id) == child.id:
                raise ValueError('A child cannot be recorded as their own mother.')

            birth_date_str = request.form.get('birth_date')
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            if birth_date > date.today():
                raise ValueError('Birth date cannot be in the future.')
            if child.dob and birth_date != child.dob:
                flash(
                    f'Note: the birth date entered ({birth_date.strftime("%d %b %Y")}) '
                    f'differs from the date of birth already on the beneficiary '
                    f'record ({child.dob.strftime("%d %b %Y")}). The schedule will '
                    f'be generated from the date entered here.',
                    'warning',
                )

            birth_weight = float(request.form.get('birth_weight')) if request.form.get('birth_weight') else None
            if birth_weight is not None and not (0 < birth_weight <= 10):
                raise ValueError('Birth weight must be between 0 and 10 kg.')

            immunization_status = request.form.get('immunization_status', 'Pending')
            growth_category = request.form.get('growth_category', 'Normal')
            feeding_type = request.form.get('feeding_type', 'Breastfed')

            child_record = ChildRecord(
                beneficiary_id=beneficiary_id,
                mother_id=mother_id,
                birth_date=birth_date,
                birth_weight=birth_weight,
                immunization_status=immunization_status,
                growth_category=growth_category,
                feeding_type=feeding_type
            )
            db.session.add(child_record)
            db.session.commit()
            flash('Child record created successfully!', 'success')
            return redirect(url_for('maternal'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering child record: {str(e)}', 'danger')

    # Only offer beneficiaries who do not already have a child record, so the
    # dropdown cannot be used to create the duplicate that the guard above
    # would then have to reject.
    already_recorded = {
        r.beneficiary_id for r in ChildRecord.query.with_entities(ChildRecord.beneficiary_id).all()
    }
    all_beneficiaries = [
        b for b in Beneficiary.query.order_by(Beneficiary.full_name).all()
        if b.id not in already_recorded
    ]
    mothers = Beneficiary.query.filter_by(gender='Female').all()
    return render_template('child_form.html', beneficiaries=all_beneficiaries, mothers=mothers)


# --- IMMUNIZATION ROUTES ---

@app.route('/immunizations')
@login_required
def immunizations():
    status_filter = request.args.get('status')
    query = ImmunizationSchedule.query

    if status_filter == 'Overdue':
        # "Overdue" is derived, not stored: a Pending dose counts as overdue
        # once its date has passed. Filter on the same rule display_status uses
        # so the dropdown and the badges agree.
        query = query.filter(
            ImmunizationSchedule.status.in_(['Pending', 'Overdue']),
            ImmunizationSchedule.given_date.is_(None),
            ImmunizationSchedule.scheduled_date < date.today(),
        )
    elif status_filter:
        query = query.filter_by(status=status_filter)

    schedules = query.order_by(ImmunizationSchedule.scheduled_date.asc()).all()
    # Read is open to every signed-in role, so the write controls are offered
    # only to the roles the POST route actually accepts. Hiding a button the
    # server would refuse anyway is a courtesy, not the enforcement.
    return render_template(
        'immunizations.html',
        immunizations=schedules,
        can_schedule=session.get('role') in ('health_worker', 'supervisor', 'admin'),
    )


@app.route('/immunizations/schedule', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor', 'admin')
def schedule_immunization():
    """Queue a dose by hand, or generate the whole schedule for a child."""
    try:
        vaccines = ensure_vaccines()
        child_records = ChildRecord.query.order_by(ChildRecord.birth_date).all()
    except Exception as e:
        flash(f'Could not load immunization data: {str(e)}', 'danger')
        return redirect(url_for('immunizations'))

    if request.method == 'POST':
        try:
            child_id = request.form.get('child_id')
            child_record = ChildRecord.query.get_or_404(child_id)

            created = generate_schedule_for(child_record, vaccines)
            db.session.commit()

            if created:
                flash(f'{created} vaccine doses queued for {child_record.beneficiary.full_name}.', 'success')
            else:
                flash('Every scheduled dose is already on file for this child.', 'info')
            return redirect(url_for('immunizations'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error generating schedule: {str(e)}', 'danger')
            return redirect(url_for('immunizations'))

    return render_template('schedule_immunization.html', vaccines=vaccines,
                           child_records=child_records)


@app.route('/immunizations/update/<int:id>', methods=['POST'])
@login_required
@role_required('health_worker', 'supervisor', 'admin')
def update_immunization(id):
    schedule = ImmunizationSchedule.query.get_or_404(id)
    try:
        schedule.status = 'Completed'
        schedule.given_date = date.today()
        schedule.administered_by = session.get('user_id')
        schedule.notes = request.form.get('notes', 'Administered on schedule')
        db.session.commit()
        flash('Immunization marked as completed!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating immunization: {str(e)}', 'danger')

    return redirect(url_for('immunizations'))


# --- MEDICINE ROUTES ---

@app.route('/medicines')
@login_required
def medicines():
    all_medicines = Medicine.query.order_by(Medicine.medicine_name.asc()).all()
    all_prescriptions = Prescription.query.order_by(Prescription.prescribed_date.desc()).all()
    return render_template('medicines.html', medicines=all_medicines, prescriptions=all_prescriptions)


@app.route('/medicines/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_medicine():
    if request.method == 'POST':
        try:
            name = request.form.get('medicine_name')
            category = request.form.get('category')
            stock = int(request.form.get('stock_quantity', 0))
            unit = request.form.get('unit', 'Tablets')
            expiry_str = request.form.get('expiry_date')
            reorder = int(request.form.get('reorder_level', 10))

            expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None

            med = Medicine(
                medicine_name=name,
                category=category,
                stock_quantity=stock,
                unit=unit,
                expiry_date=expiry,
                reorder_level=reorder
            )
            db.session.add(med)
            db.session.commit()
            flash('Medicine added to inventory!', 'success')
            return redirect(url_for('medicines'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding medicine: {str(e)}', 'danger')

    return render_template('medicine_form.html')


@app.route('/medicines/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def edit_medicine(id):
    med = Medicine.query.get_or_404(id)
    if request.method == 'POST':
        try:
            med.medicine_name = request.form.get('medicine_name')
            med.category = request.form.get('category')
            med.stock_quantity = int(request.form.get('stock_quantity', 0))
            med.unit = request.form.get('unit', 'Tablets')
            med.reorder_level = int(request.form.get('reorder_level', 10))
            expiry_str = request.form.get('expiry_date')
            med.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None

            db.session.commit()
            flash('Medicine updated successfully!', 'success')
            return redirect(url_for('medicines'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating medicine: {str(e)}', 'danger')

    return render_template('medicine_form.html', medicine=med)


@app.route('/medicines/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'supervisor')
def delete_medicine(id):
    med = Medicine.query.get_or_404(id)
    try:
        active_rx = Prescription.query.filter_by(medicine_id=id, status='Active').count()
        if active_rx:
            flash(
                f'Cannot delete {med.medicine_name}: {active_rx} active prescription(s) reference it.',
                'warning'
            )
            return redirect(url_for('medicines'))

        name = med.medicine_name
        db.session.delete(med)
        db.session.commit()
        flash(f'Medicine {name} removed from inventory.', 'success')
        return redirect(url_for('medicines'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting medicine: {str(e)}', 'danger')
        return redirect(url_for('medicines'))


@app.route('/medicines/prescribe', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def prescribe_medicine():
    if request.method == 'POST':
        try:
            beneficiary_id = request.form.get('beneficiary_id')
            medicine_id = request.form.get('medicine_id')
            dosage = request.form.get('dosage')
            duration = request.form.get('duration')
            quantity = int(request.form.get('quantity_dispensed', 1))

            med = db.session.get(Medicine, int(medicine_id)) if medicine_id else None
            if med:
                if med.stock_quantity < quantity:
                    flash(f'Insufficient stock for {med.medicine_name}. Available: {med.stock_quantity}', 'warning')
                    beneficiaries = Beneficiary.query.all()
                    medicines = Medicine.query.all()
                    return render_template('prescription_form.html', beneficiaries=beneficiaries, medicines=medicines)

                med.stock_quantity -= quantity

            prescription = Prescription(
                beneficiary_id=beneficiary_id,
                medicine_id=medicine_id,
                prescribed_by=session.get('user_id'),
                dosage=dosage,
                duration=duration,
                quantity_dispensed=quantity,
                status='Active'
            )
            db.session.add(prescription)
            db.session.commit()
            flash('Medicine prescribed and stock updated successfully!', 'success')
            return redirect(url_for('medicines'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating prescription: {str(e)}', 'danger')

    beneficiaries = Beneficiary.query.all()
    medicines = Medicine.query.all()
    return render_template('prescription_form.html', beneficiaries=beneficiaries, medicines=medicines)


# --- HOME VISIT ROUTES ---

@app.route('/visits')
@login_required
def visits():
    all_visits = HomeVisit.query.order_by(HomeVisit.visit_date.desc()).all()
    return render_template('visits.html', visits=all_visits)


@app.route('/visits/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_visit():
    if request.method == 'POST':
        try:
            household_id = request.form.get('household_id')
            visit_date_str = request.form.get('visit_date')
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
            purpose = request.form.get('purpose')
            observations = request.form.get('observations')

            visit = HomeVisit(
                household_id=household_id,
                chw_id=session.get('user_id'),
                visit_date=visit_date,
                purpose=purpose,
                observations=observations,
                status='Scheduled'
            )
            db.session.add(visit)
            db.session.commit()
            flash('Home visit scheduled successfully!', 'success')
            return redirect(url_for('visits'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error scheduling visit: {str(e)}', 'danger')

    households = Household.query.all()
    return render_template('visit_form.html', households=households)


@app.route('/visits/complete/<int:id>', methods=['POST'])
@login_required
@role_required('health_worker', 'supervisor')
def complete_visit(id):
    visit = HomeVisit.query.get_or_404(id)
    try:
        visit.status = 'Completed'
        visit.observations = request.form.get('observations', visit.observations)
        followup_str = request.form.get('followup_date')
        if followup_str:
            visit.followup_date = datetime.strptime(followup_str, '%Y-%m-%d').date()
            visit.status = 'Follow-up Required'
        db.session.commit()
        flash('Visit marked as completed!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating visit: {str(e)}', 'danger')

    return redirect(url_for('visits'))


@app.route('/visits/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'supervisor')
def delete_visit(id):
    visit = HomeVisit.query.get_or_404(id)
    try:
        date_str = visit.visit_date.strftime('%d %b %Y')
        db.session.delete(visit)
        db.session.commit()
        flash(f'Visit of {date_str} deleted.', 'success')
        return redirect(url_for('visits'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting visit: {str(e)}', 'danger')
        return redirect(url_for('visits'))


# --- REFERRAL ROUTES ---

@app.route('/referrals')
@login_required
def referrals():
    all_referrals = Referral.query.order_by(Referral.created_at.desc()).all()
    return render_template('referrals.html', referrals=all_referrals)


@app.route('/referrals/add', methods=['GET', 'POST'])
@login_required
@role_required('health_worker', 'supervisor')
def add_referral():
    if request.method == 'POST':
        try:
            beneficiary_id = request.form.get('beneficiary_id')
            reason = request.form.get('reason')
            hospital_name = request.form.get('hospital_name')
            priority = request.form.get('priority', 'Medium')

            ref = Referral(
                beneficiary_id=beneficiary_id,
                referred_by=session.get('user_id'),
                reason=reason,
                hospital_name=hospital_name,
                priority=priority,
                status='Pending'
            )
            db.session.add(ref)
            db.session.commit()
            flash('Hospital referral created successfully!', 'success')
            return redirect(url_for('referrals'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating referral: {str(e)}', 'danger')

    beneficiaries = Beneficiary.query.all()
    return render_template('referral_form.html', beneficiaries=beneficiaries)


@app.route('/referrals/update/<int:id>', methods=['POST'])
@login_required
@role_required('supervisor')
def update_referral(id):
    """Supervisors close out a referral: status, hospital outcome, feedback."""
    ref = Referral.query.get_or_404(id)
    try:
        status = request.form.get('status')
        if status in ('Pending', 'Accepted', 'Completed', 'Cancelled'):
            ref.status = status
        ref.outcome = request.form.get('outcome', ref.outcome)
        ref.feedback = request.form.get('feedback', ref.feedback)

        db.session.commit()
        flash(f'Referral for {ref.beneficiary.full_name} updated to "{ref.status}".', 'success')
        return redirect(url_for('referrals'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating referral: {str(e)}', 'danger')
        return redirect(url_for('referrals'))


@app.route('/referrals/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_referral(id):
    ref = Referral.query.get_or_404(id)
    try:
        name = ref.beneficiary.full_name
        db.session.delete(ref)
        db.session.commit()
        flash(f'Referral for {name} deleted.', 'success')
        return redirect(url_for('referrals'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting referral: {str(e)}', 'danger')
        return redirect(url_for('referrals'))


# --- REPORTS & EXPORT ENGINE ---

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


@app.route('/reports/export/<string:report_type>')
@login_required
def export_report(report_type):
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'beneficiaries':
        writer.writerow(['Health ID', 'Full Name', 'DOB', 'Gender', 'Mobile', 'Blood Group', 'Household #', 'Address'])
        records = Beneficiary.query.all()
        for b in records:
            writer.writerow([b.health_id, b.full_name, b.dob, b.gender, b.mobile, b.blood_group, b.household.household_number if b.household else '', b.household.address if b.household else ''])

    elif report_type == 'assessments':
        writer.writerow(['Date', 'Beneficiary', 'Health ID', 'Weight (kg)', 'Height (cm)', 'BMI', 'BP Systolic', 'BP Diastolic', 'Temp (F)', 'Hemoglobin', 'Blood Sugar', 'Symptoms'])
        records = HealthAssessment.query.all()
        for a in records:
            b = a.beneficiary
            writer.writerow([a.assessment_date, b.full_name if b else '', b.health_id if b else '', a.weight, a.height, a.bmi, a.bp_systolic, a.bp_diastolic, a.temperature, a.hemoglobin, a.blood_sugar, a.symptoms])

    elif report_type == 'maternal':
        writer.writerow(['Beneficiary', 'Health ID', 'LMP Date', 'EDD Date', 'ANC Visits', 'Hemoglobin', 'Blood Pressure', 'High Risk', 'High Risk Reason', 'Status'])
        records = MaternalRecord.query.all()
        for m in records:
            b = m.beneficiary
            writer.writerow([b.full_name if b else '', b.health_id if b else '', m.lmp_date, m.edd_date, m.anc_visits_count, m.hemoglobin, m.blood_pressure, 'Yes' if m.is_high_risk else 'No', m.high_risk_reason, m.status])

    elif report_type == 'immunizations':
        writer.writerow(['Beneficiary', 'Health ID', 'Vaccine', 'Scheduled Date', 'Given Date', 'Status'])
        records = ImmunizationSchedule.query.all()
        for i in records:
            b = i.beneficiary
            writer.writerow([b.full_name if b else '', b.health_id if b else '', i.vaccine.vaccine_name if i.vaccine else '', i.scheduled_date, i.given_date, i.status])

    elif report_type == 'visits':
        writer.writerow(['Household #', 'Head Name', 'Visit Date', 'Purpose', 'Observations', 'Status', 'Follow-up Date'])
        records = HomeVisit.query.all()
        for v in records:
            h = v.household
            writer.writerow([h.household_number if h else '', h.head_name if h else '', v.visit_date, v.purpose, v.observations, v.status, v.followup_date])

    elif report_type == 'referrals':
        writer.writerow(['Beneficiary', 'Health ID', 'Referral Date', 'Hospital', 'Priority', 'Reason', 'Status'])
        records = Referral.query.all()
        for r in records:
            b = r.beneficiary
            writer.writerow([b.full_name if b else '', b.health_id if b else '', r.referral_date, r.hospital_name, r.priority, r.reason, r.status])

    else:
        flash('Invalid report type requested.', 'danger')
        return redirect(url_for('reports'))

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename={report_type}_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


# --- SEED DATABASE ROUTE ---

@app.route('/seed')
@admin_required
def seed_database():
    try:
        ensure_schema()

        # Demo data is loaded once. Checking for households rather than users
        # matters now that a bootstrap admin may already exist on a database
        # that has no records yet.
        if Household.query.first() or Beneficiary.query.first():
            flash('Database already contains records; demo data was not loaded.', 'info')
            return redirect(url_for('dashboard'))

        # Create the demo field accounts that do not exist yet. This route is
        # admin-only, so an admin already exists and no second admin with a
        # published password is ever created here.
        demo_accounts = [
            ('healthworker1', 'Anita Sharma (CHW)', 'health_worker', '9876543211', 'worker123'),
            ('supervisor1', 'Dr. Rajesh Kumar', 'supervisor', '9876543212', 'super123'),
        ]
        created_accounts = []
        for username, full_name, role, phone, password in demo_accounts:
            if User.query.filter_by(username=username).first():
                continue
            account = User(username=username, full_name=full_name, role=role, phone=phone)
            account.set_password(password)
            db.session.add(account)
            created_accounts.append(username)
        db.session.commit()

        worker1 = User.query.filter_by(username='healthworker1').first()

        # Standard vaccine master list (loaded only if the table is empty).
        vaccines_by_name = {v.vaccine_name: v for v in ensure_vaccines()}

        # Seed Sample Households
        h1 = Household(household_number='HH-101', head_name='Ramesh Patil', address='12 Gram Panchayat Road, Ward 3', area='East Village', ward='Ward 3', contact_no='9123456780', economic_status='BPL')
        h2 = Household(household_number='HH-102', head_name='Suresh Verma', address='45 Primary School Lane, Ward 3', area='East Village', ward='Ward 3', contact_no='9123456781', economic_status='APL')
        h3 = Household(household_number='HH-103', head_name='Sunita Devi', address='88 Riverbank Colony, Ward 4', area='North Block', ward='Ward 4', contact_no='9123456782', economic_status='AAY')
        db.session.add_all([h1, h2, h3])
        db.session.commit()

        # Seed Sample Beneficiaries
        b1 = Beneficiary(household_id=h1.id, full_name='Priya Patil', dob=date(1996, 5, 14), gender='Female', health_id='HID-2024-0001', mobile='9123456780', blood_group='B+')
        b2 = Beneficiary(household_id=h1.id, full_name='Aarav Patil', dob=date(2023, 1, 10), gender='Male', health_id='HID-2024-0002', mobile='9123456780', blood_group='B+')
        b3 = Beneficiary(household_id=h2.id, full_name='Meena Verma', dob=date(1994, 8, 22), gender='Female', health_id='HID-2024-0003', mobile='9123456781', blood_group='O+')
        b4 = Beneficiary(household_id=h3.id, full_name='Rohan Devi', dob=date(2015, 3, 15), gender='Male', health_id='HID-2024-0004', mobile='9123456782', blood_group='A+', is_disabled=True, disability_details='Locomotor disability in left leg')

        db.session.add_all([b1, b2, b3, b4])
        db.session.commit()

        # Seed Maternal Record
        m1 = MaternalRecord(beneficiary_id=b1.id, lmp_date=date.today() - timedelta(days=120), edd_date=date.today() + timedelta(days=160), anc_visits_count=2, hemoglobin=10.2, blood_pressure='120/80', is_high_risk=True, high_risk_reason='Mild Anemia (Hb < 11.0)', status='Pregnant')
        db.session.add(m1)

        # Seed Child Record
        c1 = ChildRecord(beneficiary_id=b2.id, mother_id=b1.id, birth_weight=2.8, birth_date=date(2023, 1, 10), immunization_status='Partial', growth_category='Normal', feeding_type='Breastfed')
        db.session.add(c1)

        # Seed Health Assessment
        ha1 = HealthAssessment(beneficiary_id=b1.id, chw_id=worker1.id, assessment_date=date.today() - timedelta(days=5), weight=58.5, height=155.0, bmi=24.35, bp_systolic=120, bp_diastolic=80, temperature=98.6, hemoglobin=10.2, blood_sugar=95.0, symptoms='Mild fatigue', notes='Advised iron tablets and protein diet.')
        db.session.add(ha1)

        # Seed Immunization Schedule
        imm1 = ImmunizationSchedule(beneficiary_id=b2.id, vaccine_id=vaccines_by_name['BCG'].id, scheduled_date=date(2023, 1, 10), given_date=date(2023, 1, 10), status='Completed', administered_by=worker1.id)
        imm2 = ImmunizationSchedule(beneficiary_id=b2.id, vaccine_id=vaccines_by_name['OPV 1'].id, scheduled_date=date(2023, 3, 10), given_date=date(2023, 3, 12), status='Completed', administered_by=worker1.id)
        imm3 = ImmunizationSchedule(beneficiary_id=b2.id, vaccine_id=vaccines_by_name['Measles / Rubella 1'].id, scheduled_date=date.today() + timedelta(days=15), status='Pending')
        db.session.add_all([imm1, imm2, imm3])

        # Seed Medicines
        m_list = [
            Medicine(medicine_name='Iron & Folic Acid Tablets (IFA)', category='Supplements', stock_quantity=500, unit='Tablets', expiry_date=date(2025, 12, 31), reorder_level=100),
            Medicine(medicine_name='Paracetamol 500mg', category='Analgesic / Antipyretic', stock_quantity=300, unit='Tablets', expiry_date=date(2025, 6, 30), reorder_level=50),
            Medicine(medicine_name='ORS Packets (Oral Rehydration)', category='Hydration', stock_quantity=150, unit='Packets', expiry_date=date(2026, 1, 1), reorder_level=30),
            Medicine(medicine_name='Calcium & Vitamin D3', category='Supplements', stock_quantity=80, unit='Tablets', expiry_date=date(2025, 8, 15), reorder_level=100),
            Medicine(medicine_name='Amoxicillin Syrup 125mg', category='Antibiotics', stock_quantity=25, unit='Bottles', expiry_date=date(2024, 11, 30), reorder_level=10),
        ]
        db.session.add_all(m_list)

        # Seed Home Visit
        v1 = HomeVisit(household_id=h1.id, chw_id=worker1.id, visit_date=date.today() - timedelta(days=2), purpose='Routine ANC Check & Child Growth Monitoring', observations='Priya is taking IFA tablets regularly. Aarav is active.', status='Completed')
        v2 = HomeVisit(household_id=h3.id, chw_id=worker1.id, visit_date=date.today() + timedelta(days=3), purpose='Disability Support & General Health Check', status='Scheduled')
        db.session.add_all([v1, v2])

        # Seed Referral
        r1 = Referral(beneficiary_id=b1.id, referred_by=worker1.id, referral_date=date.today() - timedelta(days=10), reason='Severe Hemoglobin drop screening and specialized ANC ultrasound', hospital_name='District Civil Hospital', priority='High', status='Accepted', outcome='Ultrasound normal. Prescribed IV Iron sucrose infusion.')
        db.session.add(r1)

        db.session.commit()
        if created_accounts:
            flash('Sample records loaded. Demo accounts created: ' + ', '.join(created_accounts)
                  + ' (see README for the demo passwords - change them before real use).', 'success')
        else:
            flash('Sample records loaded.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error seeding database: {str(e)}', 'danger')

    return redirect(url_for('login'))


# --- ERROR HANDLERS ---

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ==========================================
# USER MANAGEMENT (ADMIN ONLY)
# ==========================================

@app.route('/admin/users')
@admin_required
def admin_users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=all_users, role_labels=ROLE_LABELS)


@app.route('/admin/users/phone/<int:id>', methods=['POST'])
@admin_required
def admin_change_phone(id):
    """Set or clear a user's contact number.

    Accounts created outside the registration form — the default admin from
    add_admin.py, for one — start with no phone, and there was previously no
    way to fill it in afterwards, so the contact column read "—" permanently.
    """
    user = User.query.get_or_404(id)
    phone = (request.form.get('phone') or '').strip()

    # An empty field clears the number rather than failing: clearing a stale
    # contact detail is a legitimate correction.
    if phone and (not phone.isdigit() or len(phone) != 10):
        flash('Phone number must be exactly 10 digits, or left blank to clear it.', 'danger')
        return redirect(url_for('admin_users'))

    user.phone = phone or None
    db.session.commit()
    flash(f'Contact number updated for {user.full_name}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/role/<int:id>', methods=['POST'])
@admin_required
def admin_change_role(id):
    user = User.query.get_or_404(id)
    new_role = request.form.get('role')

    if new_role not in ROLE_LABELS:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('admin_users'))

    # An admin must not be able to lock themselves out of the admin area.
    if user.id == session.get('user_id') and new_role != 'admin':
        flash('You cannot remove your own administrator role.', 'warning')
        return redirect(url_for('admin_users'))

    user.role = new_role
    db.session.commit()
    flash(f'{user.full_name} is now a {ROLE_LABELS[new_role]}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/toggle/<int:id>', methods=['POST'])
@admin_required
def admin_toggle_active(id):
    user = User.query.get_or_404(id)

    if user.id == session.get('user_id'):
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin_users'))

    user.is_active = not user.is_active
    db.session.commit()
    state = 'activated' if user.is_active else 'deactivated'
    flash(f'{user.full_name} has been {state}.', 'success')
    return redirect(url_for('admin_users'))


if __name__ == '__main__':
    for note in startup_warnings():
        print(f"WARNING: {note}")

    with app.app_context():
        # Creates any missing tables in the configured PostgreSQL database
        # (the database itself - e.g. your Neon project - must already exist).
        ensure_schema()

    # Debug mode exposes an interactive console that can execute code on the
    # server, so it is never on by default. Set FLASK_DEBUG=1 only while
    # developing.
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 5000))

    if debug:
        app.run(debug=True, port=port)
    else:
        print(f"  Running on http://127.0.0.1:{port}")
        print("  Debug mode is OFF. Set FLASK_DEBUG=1 to enable it during development.\n")
        app.run(debug=False, port=port)
