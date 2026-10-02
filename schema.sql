-- ============================================================
-- CHW Digital Record System - PostgreSQL schema (Neon)
-- ============================================================
-- Matches the SQLAlchemy models in app.py. The app also creates any missing
-- tables by itself on first request, so running this file is optional; it is
-- provided for manual setup (Neon SQL Editor, psql) and for documentation.
--
-- Referential integrity policy
--   * Clinical records CASCADE: deleting a household removes its
--     beneficiaries and everything recorded about them.
--   * Records that carry accountability or inventory meaning RESTRICT:
--     user foreign keys on visits / assessments / prescriptions / referrals
--     (accounts are deactivated, never deleted) and prescriptions.medicine_id.
--
-- Enumerations are VARCHAR + CHECK (not native ENUM types) so that they are
-- identical to what SQLAlchemy creates and easy to extend.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          VARCHAR(13)  NOT NULL DEFAULT 'health_worker' CHECK (role IN ('admin','health_worker','supervisor')),
    phone         VARCHAR(15),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

CREATE TABLE IF NOT EXISTS households (
    id               SERIAL PRIMARY KEY,
    household_number VARCHAR(50)  NOT NULL UNIQUE,
    head_name        VARCHAR(100) NOT NULL,
    address          TEXT         NOT NULL,
    area             VARCHAR(100) NOT NULL,
    ward             VARCHAR(50)  NOT NULL,
    contact_no       VARCHAR(15),
    economic_status  VARCHAR(3)   DEFAULT 'BPL' CHECK (economic_status IN ('APL','BPL','AAY')),
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_households_area ON households (area);
CREATE INDEX IF NOT EXISTS idx_households_ward ON households (ward);

CREATE TABLE IF NOT EXISTS beneficiaries (
    id                 SERIAL PRIMARY KEY,
    household_id       INTEGER      NOT NULL REFERENCES households (id) ON DELETE CASCADE,
    full_name          VARCHAR(100) NOT NULL,
    dob                DATE         NOT NULL,
    gender             VARCHAR(6)   NOT NULL CHECK (gender IN ('Male','Female','Other')),
    health_id          VARCHAR(50)  NOT NULL UNIQUE,
    mobile             VARCHAR(15),
    blood_group        VARCHAR(3) CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    is_disabled        BOOLEAN      NOT NULL DEFAULT FALSE,
    disability_details TEXT,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_household ON beneficiaries (household_id);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_gender    ON beneficiaries (gender);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_dob       ON beneficiaries (dob);

CREATE TABLE IF NOT EXISTS health_assessments (
    id              SERIAL PRIMARY KEY,
    beneficiary_id  INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    chw_id          INTEGER REFERENCES users (id) ON DELETE RESTRICT,
    assessment_date DATE,
    weight          DOUBLE PRECISION,  -- kg
    height          DOUBLE PRECISION,  -- cm
    bmi             DOUBLE PRECISION,
    bp_systolic     INTEGER,
    bp_diastolic    INTEGER,
    temperature     DOUBLE PRECISION,  -- as entered in the form
    hemoglobin      DOUBLE PRECISION,  -- g/dL
    blood_sugar     DOUBLE PRECISION,  -- mg/dL
    symptoms        TEXT,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ha_beneficiary ON health_assessments (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_ha_chw         ON health_assessments (chw_id);
CREATE INDEX IF NOT EXISTS idx_ha_date        ON health_assessments (assessment_date);

CREATE TABLE IF NOT EXISTS maternal_records (
    id               SERIAL PRIMARY KEY,
    beneficiary_id   INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    lmp_date         DATE    NOT NULL,
    edd_date         DATE    NOT NULL,
    anc_visits_count INTEGER DEFAULT 0,
    pnc_visits_count INTEGER DEFAULT 0,
    hemoglobin       DOUBLE PRECISION,
    blood_pressure   VARCHAR(20),
    is_high_risk     BOOLEAN DEFAULT FALSE,
    high_risk_reason TEXT,
    delivery_date    DATE,
    delivery_type    VARCHAR(8) CHECK (delivery_type IN ('Normal','Cesarean','Assisted')),
    delivery_place   VARCHAR(200),
    baby_weight      DOUBLE PRECISION,
    status           VARCHAR(9) DEFAULT 'Pregnant' CHECK (status IN ('Pregnant','Delivered','Postnatal','Closed')),
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mr_beneficiary ON maternal_records (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_mr_status      ON maternal_records (status);

CREATE TABLE IF NOT EXISTS child_records (
    id                  SERIAL PRIMARY KEY,
    beneficiary_id      INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    mother_id           INTEGER REFERENCES beneficiaries (id) ON DELETE SET NULL,
    birth_weight        DOUBLE PRECISION,
    birth_date          DATE    NOT NULL,
    immunization_status VARCHAR(8)  DEFAULT 'Pending' CHECK (immunization_status IN ('Pending','Partial','Complete')),
    growth_category     VARCHAR(20) DEFAULT 'Normal' CHECK (growth_category IN ('Normal','Underweight','Severely Underweight','Overweight')),
    feeding_type        VARCHAR(9) CHECK (feeding_type IN ('Breastfed','Formula','Mixed')),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cr_beneficiary ON child_records (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_cr_mother      ON child_records (mother_id);

CREATE TABLE IF NOT EXISTS vaccines (
    id                SERIAL PRIMARY KEY,
    vaccine_name      VARCHAR(100) NOT NULL,
    target_age_months INTEGER      NOT NULL,   -- 0 = at birth
    dose_number       INTEGER      DEFAULT 1,
    description       TEXT
);

CREATE TABLE IF NOT EXISTS immunization_schedules (
    id              SERIAL PRIMARY KEY,
    beneficiary_id  INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    vaccine_id      INTEGER NOT NULL REFERENCES vaccines (id),
    scheduled_date  DATE    NOT NULL,
    given_date      DATE,
    status          VARCHAR(9) DEFAULT 'Pending' CHECK (status IN ('Pending','Completed','Missed','Overdue')),
    administered_by INTEGER REFERENCES users (id),
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_is_beneficiary ON immunization_schedules (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_is_vaccine     ON immunization_schedules (vaccine_id);
CREATE INDEX IF NOT EXISTS idx_is_date        ON immunization_schedules (scheduled_date);
CREATE INDEX IF NOT EXISTS idx_is_status      ON immunization_schedules (status);

CREATE TABLE IF NOT EXISTS medicines (
    id             SERIAL PRIMARY KEY,
    medicine_name  VARCHAR(200) NOT NULL,
    category       VARCHAR(100) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    unit           VARCHAR(50) DEFAULT 'Tablets',
    expiry_date    DATE,
    reorder_level  INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id                 SERIAL PRIMARY KEY,
    beneficiary_id     INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    medicine_id        INTEGER NOT NULL REFERENCES medicines (id),
    prescribed_by      INTEGER REFERENCES users (id),
    prescribed_date    DATE,
    dosage             VARCHAR(100) NOT NULL,
    duration           VARCHAR(100) NOT NULL,
    quantity_dispensed INTEGER DEFAULT 0,
    status             VARCHAR(12) DEFAULT 'Active' CHECK (status IN ('Active','Completed','Discontinued'))
);
CREATE INDEX IF NOT EXISTS idx_rx_beneficiary ON prescriptions (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_rx_medicine    ON prescriptions (medicine_id);
CREATE INDEX IF NOT EXISTS idx_rx_status      ON prescriptions (status);

CREATE TABLE IF NOT EXISTS home_visits (
    id             SERIAL PRIMARY KEY,
    household_id   INTEGER NOT NULL REFERENCES households (id) ON DELETE CASCADE,
    chw_id         INTEGER REFERENCES users (id),
    visit_date     DATE NOT NULL,
    purpose        TEXT NOT NULL,
    observations   TEXT,
    followup_date  DATE,
    followup_notes TEXT,
    status         VARCHAR(18) DEFAULT 'Scheduled' CHECK (status IN ('Scheduled','Completed','Cancelled','Follow-up Required')),
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hv_household  ON home_visits (household_id);
CREATE INDEX IF NOT EXISTS idx_hv_chw        ON home_visits (chw_id);
CREATE INDEX IF NOT EXISTS idx_hv_visit_date ON home_visits (visit_date);
CREATE INDEX IF NOT EXISTS idx_hv_status     ON home_visits (status);

CREATE TABLE IF NOT EXISTS referrals (
    id             SERIAL PRIMARY KEY,
    beneficiary_id INTEGER NOT NULL REFERENCES beneficiaries (id) ON DELETE CASCADE,
    referred_by    INTEGER REFERENCES users (id),
    referral_date  DATE,
    reason         TEXT NOT NULL,
    hospital_name  VARCHAR(200) NOT NULL,
    priority       VARCHAR(9) DEFAULT 'Medium' CHECK (priority IN ('Low','Medium','High','Emergency')),
    status         VARCHAR(9) DEFAULT 'Pending' CHECK (status IN ('Pending','Accepted','Completed','Cancelled')),
    outcome        TEXT,
    feedback       TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ref_beneficiary ON referrals (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_ref_priority    ON referrals (priority);
CREATE INDEX IF NOT EXISTS idx_ref_status      ON referrals (status);
