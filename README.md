# Digital Record System for Community Health Worker (CHW)

A modular Flask application backed by **PostgreSQL on Neon** and deployable to **Vercel**. Built for the **120-Mark B.Sc. IT Final Year Community Engagement Project**.

---

## 🛠 Tech Stack

- **Backend:** Python 3.12, Flask, Flask-SQLAlchemy 3 / SQLAlchemy 2, psycopg2
- **Database:** PostgreSQL (Neon serverless Postgres)
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5.3, Bootstrap Icons, Font Awesome 6
- **Security:** Role-based access control, per-session CSRF tokens, Werkzeug password hashing
- **Architecture:** Relational Schema (12 Tables with FK Constraints, Cascades, CHECK constraints & Indexes), Clean Routing, Fault-Tolerant Session Management

---

## 🔐 Role-Based Access Control

Access is enforced server-side by two decorators in `app.py`:

| Decorator | Effect |
| :--- | :--- |
| `login_required` | Any signed-in user. Redirects anonymous visitors to login. |
| `role_required('a', 'b')` | Restricts **writes** to the listed roles. Admins always pass, and every role may still **read** the module, so a CHW can browse the whole system. |
| `admin_required` | Strict. The admin area is unreadable by non-admins, not just unwritable. |

What each role can do:

| Action | CHW | Supervisor | Admin |
| :--- | :--- | :--- | :--- |
| View all modules | ✅ | ✅ | ✅ |
| Add / edit households, beneficiaries, medicines | ✅ | ✅ | ✅ |
| Log vitals, maternal, immunizations, visits | ✅ | ✅ | ✅ |
| Prescribe medicine & dispense stock | ✅ | ✅ | ✅ |
| Delete households, beneficiaries, visits | ❌ | ✅ | ✅ |
| Close out a referral (status + outcome) | ❌ | ✅ | ✅ |
| Delete a referral | ❌ | ❌ | ✅ |
| Manage user roles / enable accounts | ❌ | ❌ | ✅ |
| Run `/seed` | ❌ | ❌ | ✅ |

Blocked attempts return a styled **403** page rather than a raw error. A self-registration
can only ever create a `health_worker` — roles are assigned by an admin from
**User Management**, so the signup form cannot be used to escalate privileges.

## 🛡️ CSRF Protection

Every state-changing POST must carry a per-session token:

- `generate_csrf_token()` mints a token on first use and stores it in the session.
- `csrf_token()` is injected into every form as a hidden `_csrf_token` input.
- `@app.before_request enforce_csrf` compares the submitted token against the session
  using `hmac.compare_digest` (constant-time) and returns 403 on mismatch or absence.

This is hand-rolled rather than Flask-WTF so the project carries no extra dependency,
and it is easy to demonstrate in a viva.

---

## 📁 Directory Structure

```text
/digital record system for community health workers
│── app.py                 # Main Flask Application (Models, Routes, Handlers)
│── config.py              # Configuration, env vars & startup safety checks
│── wsgi.py                # WSGI entry point for non-Vercel hosts (gunicorn)
│── add_admin.py           # One-off utility: create the default admin account
│── api/index.py           # Vercel serverless entry point
│── vercel.json            # Vercel routing/build config
│── schema.sql             # Full PostgreSQL schema DDL (optional; app self-creates tables)
│── seed.sql               # Production-grade Seed Data SQL script
│── requirements.txt       # Python Dependencies
│── .env.example           # Template listing the environment variables
│── README.md              # Project Documentation & Quick Start Guide
│── /templates             # Jinja2 Templates (Bootstrap 5.3)
│   │── base.html          # Responsive Layout, Navbar & Sidebar
│   │── login.html         # User Authentication
│   │── dashboard.html     # Dynamic Analytics Dashboard
│   │── households.html    # Household Management
│   │── household_form.html# Add/Edit Household
│   │── beneficiaries.html # Beneficiary Registry
│   │── beneficiary_form.html # Add Beneficiary
│   │── beneficiary_detail.html # 360° Health Profile
│   │── assessments.html   # Health Vitals & Assessment Log
│   │── assessment_form.html# Log Vitals (BMI, BP, Temp, Hb)
│   │── maternal.html      # Maternal & Child Health Tracker
│   │── maternal_form.html # Register Pregnancy & High-Risk Alerts
│   │── immunizations.html # Vaccine Scheduler & Due Date Tracker
│   │── medicines.html     # Medicine Inventory & Dispensing
│   │── medicine_form.html # Add Medicine
│   │── visits.html        # CHW Home Visit Management
│   │── visit_form.html    # Schedule Home Visit
│   │── referrals.html     # Hospital Escalation Engine
│   │── referral_form.html # Create Referral
│   │── reports.html       # Analytics & CSV Export Engine
│   │── 404.html           # Graceful Error Page
│   └── 500.html           # Server Error Handler
└── /static
    │── /css
    │   └── style.css      # Custom Teal Healthcare Theme
    └── /js
        └── main.js        # Form validation, Auto-dismiss, BMI/EDD calc
```

---

## 🚀 Deploy to Vercel + Neon (step by step)

### 1. Create the Neon database
1. Sign in at [neon.tech](https://neon.tech) and create a project.
2. Open **Connect** and copy the **pooled** connection string (the host contains `-pooler`). It looks like  
   `postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require`

> Shortcut: in Vercel, **Storage → Create → Neon** (or the Marketplace integration) creates the database and sets `DATABASE_URL` / `POSTGRES_URL` for you. The app reads either.

### 2. Push the project to GitHub
Upload this folder to a GitHub repository (`.env` is git-ignored).

### 3. Import into Vercel
1. **Add New → Project**, pick the repository. Framework preset: **Other**. Leave build/output settings empty.
2. Under **Environment Variables** add:

| Variable | Value |
| :--- | :--- |
| `SECRET_KEY` | long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | the Neon connection string (skip if the Neon integration already set it) |
| `BOOTSTRAP_ADMIN_USERNAME` | `admin` (optional, this is the default) |
| `BOOTSTRAP_ADMIN_PASSWORD` | the password for your first admin (8+ characters) |

3. Click **Deploy**.

### 4. First run
- On the first request the app **creates all 12 tables automatically** in Neon (a Postgres advisory lock stops concurrent cold starts from colliding) and creates the admin from `BOOTSTRAP_ADMIN_*`.
- Sign in, then (optional) visit `/seed` as admin to load sample households, beneficiaries, vaccines, etc.
- Afterwards you can delete `BOOTSTRAP_ADMIN_PASSWORD` from Vercel.

### Notes
- Cookies are automatically `Secure` on Vercel (HTTPS).
- Connection pooling is deliberately tiny (`pool_size=1`) because each serverless instance handles one request at a time; Neon's pooler does the real pooling.
- Neon computes auto-suspend when idle, so the first request after a pause can take a second or two. `pool_pre_ping` reconnects transparently.

---

## 💻 Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in SECRET_KEY and DATABASE_URL
set -a; . ./.env; set +a          # PowerShell: $env:DATABASE_URL = "..."
python app.py
```

`DATABASE_URL` can be your Neon string (easiest) or a local Postgres, e.g.
`postgresql://postgres:postgres@localhost:5432/chw_system` (create the empty database first: `createdb chw_system`).

### Optional: set up via SQL instead of the auto-create
Paste `schema.sql` (then, for demo data, `seed.sql`) into the **Neon SQL Editor**, or run `python seed_now.py`.
The users in `seed.sql` have a placeholder password hash; run `python reset_passwords.py` to give them a real password, or `python add_admin.py` to create an admin.

---

## 🔐 Default Login Credentials

These apply to the `/seed` route, which creates the `healthworker1` and `supervisor1`
accounts with properly hashed passwords. The admin is whichever account you
created with `BOOTSTRAP_ADMIN_*` (or `add_admin.py`).

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` (or your bootstrap username) | the `BOOTSTRAP_ADMIN_PASSWORD` you set | Full System Access |
| **Community Health Worker (CHW)** | `healthworker1` | `worker123` | Field Data Collection & Vitals Logging |
| **Medical Supervisor** | `supervisor1` | `super123` | Referral Approval & High-Risk Case Review |

> Demo passwords are public in this README: change them (or do not run `/seed`) on any real deployment.

---

## 📊 10 Core Modules Summary (120 Marks Alignment)

1. **Authentication & Role Management (10 Marks):** Role-based access (Admin, CHW, Supervisor) enforced server-side, password hashing using `werkzeug.security`, admin-only user management.
2. **Household & Family Registration (15 Marks):** Household profiling, socio-economic tracking (APL/BPL/AAY), area/ward mapping.
3. **Beneficiary & Member Management (15 Marks):** Unique Health IDs (`HID-2024-XXXX`), disability status, age/gender profiling.
4. **Health Assessment & Vitals Logging (15 Marks):** Periodic vitals logging with auto-calculated BMI, BP alerts, temperature, Hemoglobin, and symptoms.
5. **Maternal & Child Health (MCH) (15 Marks):** Pregnancy tracking, auto-calculated EDD (LMP + 280 days), high-risk pregnancy tags, child growth classification.
6. **Immunization & Vaccine Scheduler (10 Marks):** National Immunization Schedule tracking, vaccine inventory, due/overdue status badges.
7. **Medicine Distribution & Inventory (10 Marks):** Medicine stock level tracking, low-stock reorder alerts, dispensing history.
8. **Home Visit Log & Inspection Engine (10 Marks):** Field visit scheduling, observations, follow-up flags, and completion tracking.
9. **Referral & Hospital Escalation (10 Marks):** Escalation of critical cases to district/tertiary hospitals with priority flags (Emergency, High, Medium).
10. **Analytics, Reports & Export Engine (10 Marks):** Dynamic dashboard metrics, real-time counters, and CSV exports for all datasets.

---

## 🎯 Viva Presentation Key Points

- **Fault Tolerance:** Handled gracefully with Flask try-except blocks, session rollbacks, and custom 403/404/500 handlers.
- **Authorization:** Every write is checked against the signed-in user's role; reads stay open so field staff can browse. Deletes cascade through SQLAlchemy relationships, and a medicine with active prescriptions is refused rather than orphaned.
- **Relational Integrity:** Foreign Key constraints with `ON DELETE CASCADE` prevent orphan records across households, beneficiaries, and visits. Constraints that would destroy accountability or inventory history deliberately use `ON DELETE RESTRICT` instead — see the referential integrity policy at the top of `schema.sql`.
- **Auto-Calculations:** BMI (Height/Weight), EDD (LMP + 280 days), and Age (from DOB) are auto-computed client-side and server-side.
- **Export Engine:** Native CSV generation via Python `io.StringIO` streaming response for real-time reports.
