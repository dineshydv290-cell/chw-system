-- ============================================================
-- CHW Digital Record System - demo seed data (PostgreSQL / Neon)
-- ============================================================
-- Run schema.sql first (or open the app once so it creates the tables).
-- Run this file ONCE, on an empty database: it uses explicit ids so that child
-- rows can point at their parents.
--
-- The three user rows carry the placeholder 'SET_VIA_SEED_ROUTE', which is not
-- a password hash, so those accounts cannot log in until you run
--     python reset_passwords.py
-- Alternatively skip this file and use the admin-only /seed route in the app,
-- which creates demo data with working accounts.
-- ============================================================

BEGIN;

INSERT INTO users (username, password_hash, full_name, role, phone, is_active) VALUES
('admin',         'SET_VIA_SEED_ROUTE', 'Rajesh Kumar Sharma',    'admin',         '9876543210', TRUE),
('healthworker1', 'SET_VIA_SEED_ROUTE', 'Sunita Devi Patel',      'health_worker', '9845123456', TRUE),
('supervisor1',   'SET_VIA_SEED_ROUTE', 'Mohan Lal Verma',        'supervisor',    '9812345678', TRUE);


-- ============================================================
-- HOUSEHOLDS
-- ============================================================
INSERT INTO households (household_number, head_name, address, area, ward, contact_no, economic_status) VALUES
('HH-001', 'Ramesh Chandra Gupta',   'House No. 12, Shiv Nagar Colony, Near Temple',   'Shiv Nagar',   'Ward 4',  '9871234567', 'BPL'),
('HH-002', 'Lakshmi Bai Yadav',      'B-45, Indira Nagar, Main Road',                  'Indira Nagar', 'Ward 7',  '9856789012', 'APL'),
('HH-003', 'Mohammad Aslam Khan',    'Plot 8, Muslim Colony, Near Masjid',              'Old City',     'Ward 2',  '9823456701', 'BPL'),
('HH-004', 'Prabhavati Suresh Nair', 'Flat 3B, Krishna Apartments, Civil Lines',        'Civil Lines',  'Ward 11', '9867890123', 'APL'),
('HH-005', 'Harpal Singh Dhaliwal',  '67, Guru Nanak Pura, Behind Gurdwara',            'Guru Nanak Pura', 'Ward 6', '9898765432', 'AAY');


-- ============================================================
-- BENEFICIARIES
-- ============================================================
INSERT INTO beneficiaries (household_id, full_name, dob, gender, health_id, mobile, blood_group, is_disabled, disability_details) VALUES
-- HH-001
(1, 'Kiran Gupta',           '1995-03-14', 'Female', 'CHW-BEN-0001', '9871234560', 'B+',      FALSE, NULL),
(1, 'Aryan Gupta',           '2022-08-20', 'Male',   'CHW-BEN-0002', NULL,         NULL, FALSE, NULL),
-- HH-002
(2, 'Savita Yadav',          '1989-11-05', 'Female', 'CHW-BEN-0003', '9856789013', 'O+',      FALSE, NULL),
(2, 'Rohan Yadav',           '2020-01-15', 'Male',   'CHW-BEN-0004', NULL,         'O+',      FALSE, NULL),
-- HH-003
(3, 'Nasreen Khan',          '1997-06-22', 'Female', 'CHW-BEN-0005', '9823456702', 'A+',      FALSE, NULL),
(3, 'Abdul Rehman Khan',     '1970-09-30', 'Male',   'CHW-BEN-0006', '9823456700', 'B-',      TRUE, 'Partial paralysis of left leg following stroke in 2019'),
-- HH-004
(4, 'Deepa Nair',            '2001-04-18', 'Female', 'CHW-BEN-0007', '9867890124', 'AB+',     FALSE, NULL),
-- HH-005
(5, 'Gurpreet Kaur Dhaliwal','1993-07-10', 'Female', 'CHW-BEN-0008', '9898765430', 'A+',      FALSE, NULL),
(5, 'Tejinder Singh Dhaliwal','1965-02-28','Male',   'CHW-BEN-0009', '9898765432', 'B+',      FALSE, NULL),
(5, 'Paramjit Kaur',         '2023-05-02', 'Female', 'CHW-BEN-0010', NULL,         NULL, FALSE, NULL);


-- ============================================================
-- HEALTH ASSESSMENTS
-- ============================================================
INSERT INTO health_assessments (beneficiary_id, chw_id, assessment_date, weight, height, bmi, bp_systolic, bp_diastolic, temperature, hemoglobin, blood_sugar, symptoms, notes) VALUES
(1,  2, '2024-09-05', 52.5, 158.0, 21.04, 110, 70, 37.0, 10.2, 90.0,  'Mild fatigue, occasional headache',        'Iron deficiency suspected; IFA prescribed'),
(3,  2, '2024-09-10', 60.0, 162.0, 22.86, 118, 76, 36.8, 11.5, 95.0,  'None',                                     'All parameters normal'),
(5,  2, '2024-09-12', 48.0, 155.0, 19.97, 100, 65, 36.6, 9.5,  88.0,  'Dizziness, fatigue, pallor',               'Severe anaemia; referred to PHC for further workup'),
(6,  2, '2024-09-14', 65.0, 168.0, 23.03, 150, 95, 37.2, 12.0, 185.0, 'Hypertension, uncontrolled blood sugar',   'Diabetic and hypertensive; medication counselling done; referred to CHC'),
(8,  2, '2024-09-18', 58.0, 160.0, 22.66, 112, 74, 36.9, 11.8, 92.0,  'Mild back pain in third trimester',        'Advised rest and micronutrient supplementation; ANC card updated');


-- ============================================================
-- MATERNAL RECORDS
-- ============================================================
INSERT INTO maternal_records (beneficiary_id, lmp_date, edd_date, anc_visits_count, pnc_visits_count, hemoglobin, blood_pressure, is_high_risk, high_risk_reason, delivery_date, delivery_type, delivery_place, baby_weight, status) VALUES
(1,  '2024-02-10', '2024-11-17', 4, 0, 10.2, '110/70', FALSE, NULL,                             NULL,         NULL,       NULL,                     NULL, 'Pregnant'),
(5,  '2024-03-01', '2024-12-06', 3, 0,  9.5, '100/65', TRUE, 'Severe anaemia, low BMI',        NULL,         NULL,       NULL,                     NULL, 'Pregnant'),
(8,  '2024-01-15', '2024-10-22', 6, 0, 11.8, '112/74', FALSE, NULL,                             NULL,         NULL,       NULL,                     NULL, 'Pregnant');


-- ============================================================
-- CHILD RECORDS
-- ============================================================
INSERT INTO child_records (beneficiary_id, mother_id, birth_weight, birth_date, immunization_status, growth_category, feeding_type) VALUES
(2,  1, 2.85, '2022-08-20', 'Partial',  'Normal',      'Breastfed'),
(10, 8, 2.60, '2023-05-02', 'Pending',  'Underweight', 'Breastfed');


-- ============================================================
-- VACCINES  (National Immunisation Schedule — India)
-- ============================================================
INSERT INTO vaccines (vaccine_name, target_age_months, dose_number, description) VALUES
('BCG',                    0,  1, 'Bacillus Calmette-Guerin — protection against tuberculosis; given at birth'),
('OPV 0',                  0,  1, 'Oral Polio Vaccine — zero dose given at birth'),
('Hepatitis B (Birth)',     0,  1, 'Hepatitis B vaccine — birth dose'),
('OPV 1',                  6,  1, 'Oral Polio Vaccine — first dose at 6 weeks'),
('OPV 2',                  10, 2, 'Oral Polio Vaccine — second dose at 10 weeks'),
('OPV 3',                  14, 3, 'Oral Polio Vaccine — third dose at 14 weeks'),
('DPT 1',                  6,  1, 'Diphtheria, Pertussis, Tetanus — first dose'),
('DPT 2',                  10, 2, 'Diphtheria, Pertussis, Tetanus — second dose'),
('DPT 3',                  14, 3, 'Diphtheria, Pertussis, Tetanus — third dose'),
('DPT Booster 1',          16, 1, 'DPT booster dose at 16–24 months'),
('Hepatitis B 1',          6,  2, 'Hepatitis B — second dose at 6 weeks'),
('Hepatitis B 2',          10, 3, 'Hepatitis B — third dose at 10 weeks'),
('Hib 1',                  6,  1, 'Haemophilus influenzae type b — first dose'),
('Hib 2',                  10, 2, 'Haemophilus influenzae type b — second dose'),
('Hib 3',                  14, 3, 'Haemophilus influenzae type b — third dose'),
('IPV',                    14, 1, 'Inactivated Polio Vaccine — fractional first dose'),
('Rotavirus 1',             6, 1, 'Rotavirus vaccine — first dose'),
('Rotavirus 2',            10, 2, 'Rotavirus vaccine — second dose'),
('PCV 1',                   6, 1, 'Pneumococcal Conjugate Vaccine — first dose'),
('PCV 2',                  14, 2, 'Pneumococcal Conjugate Vaccine — second dose'),
('Measles / MR 1',          9, 1, 'Measles-Rubella — first dose at 9–12 months'),
('Vitamin A (1st)',          9, 1, 'Vitamin A supplementation — first dose'),
('JE 1',                   12, 1, 'Japanese Encephalitis — first dose (endemic areas)'),
('Measles / MR 2',         16, 2, 'Measles-Rubella — second dose (16–24 months)'),
('Vitamin A (2nd)',         16, 2, 'Vitamin A supplementation — subsequent doses'),
('DPT Booster 2',          60, 2, 'DPT second booster dose at 5 years'),
('OPV Booster',            60, 1, 'OPV booster at 5 years'),
('Td',                    120, 1, 'Tetanus-diphtheria at 10 years'),
('Td (16 yr)',             192, 2, 'Tetanus-diphtheria at 16 years'),
('TT (Pregnancy 1)',        -1, 1, 'Tetanus Toxoid — first dose in pregnancy'),
('TT (Pregnancy 2)',        -1, 2, 'Tetanus Toxoid — second dose in pregnancy 4 weeks after first');


-- ============================================================
-- IMMUNIZATION SCHEDULES
-- ============================================================
INSERT INTO immunization_schedules (beneficiary_id, vaccine_id, scheduled_date, given_date, status, administered_by, notes) VALUES
-- Aryan Gupta (child, born Aug 2022) — partially immunised
(2,  1,  '2022-08-20', '2022-08-20', 'Completed', 2, 'BCG scar noted at 6-week visit'),
(2,  7,  '2022-10-01', '2022-10-02', 'Completed', 2, 'DPT-1 given at sub-centre'),
(2,  8,  '2022-11-01', '2022-11-03', 'Completed', 2, 'DPT-2 given at outreach session'),
(2,  21, '2023-05-20', NULL,          'Missed',    NULL, 'Family was away; to be rescheduled'),
(2,  24, '2023-12-20', NULL,          'Pending',   NULL, 'MR-2 due — remind during next home visit'),
-- Paramjit Kaur (infant, born May 2023) — birth doses pending follow-up
(10, 1,  '2023-05-02', '2023-05-02', 'Completed', 2, 'BCG given at hospital at birth'),
(10, 2,  '2023-05-02', '2023-05-02', 'Completed', 2, 'OPV-0 given at birth'),
(10, 4,  '2023-06-13', NULL,          'Overdue',   NULL, 'OPV-1 overdue; family not contacted'),
(10, 7,  '2023-06-13', NULL,          'Overdue',   NULL, 'DPT-1 overdue — prioritise for next session'),
(10, 21, '2024-02-02', NULL,          'Pending',   NULL, 'MR-1 scheduled at 9 months');


-- ============================================================
-- MEDICINES
-- ============================================================
INSERT INTO medicines (medicine_name, category, stock_quantity, unit, expiry_date, reorder_level) VALUES
('Iron-Folic Acid (IFA) 100 mg + 500 mcg', 'Micronutrient',    500, 'Tablets',  '2026-03-31', 100),
('Oral Rehydration Salts (ORS)',            'Rehydration',      200, 'Sachets',  '2025-12-31',  50),
('Zinc Sulfate 20 mg',                      'Micronutrient',    300, 'Tablets',  '2025-09-30',  50),
('Paracetamol 500 mg',                      'Analgesic',        400, 'Tablets',  '2025-06-30',  80),
('Amoxicillin 250 mg',                      'Antibiotic',       150, 'Capsules', '2025-11-30',  30),
('Cotrimoxazole 480 mg',                    'Antibiotic',       100, 'Tablets',  '2025-10-31',  20),
('Vitamin A 200,000 IU',                    'Micronutrient',     80, 'Capsules', '2025-08-31',  20),
('Metronidazole 400 mg',                    'Antiparasitic',    120, 'Tablets',  '2025-07-31',  25),
('Albendazole 400 mg',                      'Antiparasitic',    200, 'Tablets',  '2025-12-31',  30),
('Calcium + Vitamin D3 Tablet',             'Micronutrient',    250, 'Tablets',  '2026-01-31',  50);


-- ============================================================
-- PRESCRIPTIONS
-- ============================================================
INSERT INTO prescriptions (beneficiary_id, medicine_id, prescribed_by, prescribed_date, dosage, duration, quantity_dispensed, status) VALUES
(1,  1,  2, '2024-09-05', '1 tablet once daily after meals',  '90 days',  90, 'Active'),
(1,  10, 2, '2024-09-05', '1 tablet twice daily after meals', '90 days',  90, 'Active'),
(5,  1,  2, '2024-09-12', '1 tablet once daily after meals',  '60 days',  60, 'Active'),
(2,  2,  2, '2024-08-01', '1 sachet dissolved in 200 ml water as needed', 'As needed', 10, 'Completed'),
(4,  3,  2, '2024-08-15', '1 tablet once daily',              '14 days',  14, 'Completed');


-- ============================================================
-- HOME VISITS
-- ============================================================
INSERT INTO home_visits (household_id, chw_id, visit_date, purpose, observations, followup_date, followup_notes, status) VALUES
(1, 2, '2024-09-06',
 'ANC follow-up and IFA compliance check for Kiran Gupta',
 'Mother consuming IFA regularly; mild nausea reported. Advised to take tablet at night with warm milk. Birth preparedness plan discussed.',
 '2024-10-06',
 'Check IFA compliance, weight gain, and ANC card update.',
 'Completed'),

(3, 2, '2024-09-13',
 'High-risk pregnancy follow-up for Nasreen Khan; health check of Abdul Rehman Khan',
 'Nasreen appears very pale — hemoglobin critically low. Referred to PHC. Abdul''s BP uncontrolled at 150/95; diabetes education provided.',
 '2024-09-27',
 'Confirm Nasreen attended PHC. Recheck Abdul''s BP and blood sugar.',
 'Follow-up Required'),

(5, 2, '2024-09-19',
 'Third-trimester ANC visit for Gurpreet Kaur; infant growth monitoring for Paramjit',
 'Gurpreet''s vitals stable; foetal movement normal. Paramjit''s weight below the growth curve — advised on complementary feeding; referred to VHND.',
 '2024-10-10',
 'Growth monitoring, immunisation catch-up for Paramjit.',
 'Completed'),

(2, 2, '2024-09-22',
 'Immunisation status check and diarrhoea management for Rohan Yadav',
 'ORS sachets provided; diarrhoea resolving. Vaccination card reviewed — MR-2 pending.',
 '2024-10-05',
 'Confirm diarrhoea resolved; schedule MR-2 at next session.',
 'Follow-up Required'),

(4, 2, '2024-09-25',
 'Routine household visit; adolescent health counselling for Deepa Nair',
 'Deepa menstrual health counselled; anaemia screening done (Hb 12.5 g/dL — normal). PCOD awareness shared.',
 NULL,
 NULL,
 'Completed');


-- ============================================================
-- REFERRALS
-- ============================================================
INSERT INTO referrals (beneficiary_id, referred_by, referral_date, reason, hospital_name, priority, status, outcome, feedback) VALUES
(5,  2, '2024-09-12',
 'Severe anaemia during pregnancy (Hb 9.5 g/dL) — requires IV iron infusion and obstetrician review',
 'Primary Health Centre, Sector 8',
 'High',
 'Pending',
 NULL,
 NULL),

(6,  2, '2024-09-14',
 'Uncontrolled hypertension (150/95 mmHg) and elevated blood sugar (185 mg/dL) — needs specialist management',
 'Community Health Centre (CHC), District Hospital Road',
 'High',
 'Accepted',
 'Patient seen by physician; antihypertensive and oral hypoglycaemic medication prescribed. Follow-up in 2 weeks.',
 'PHC confirmed patient received treatment; family cooperative'),

(10, 2, '2024-09-19',
 'Infant Paramjit Kaur (4 months) shows weight faltering — weight 4.1 kg against expected 6.0 kg; classified Severely Underweight',
 'Nutrition Rehabilitation Centre (NRC), District Hospital',
 'Medium',
 'Pending',
 NULL,
 NULL);

-- ============================================================
-- Explicit ids do not advance PostgreSQL sequences. Move every sequence past
-- the largest id so that the next row created by the app does not collide.
-- ============================================================
SELECT setval(pg_get_serial_sequence('users', 'id'),                  (SELECT MAX(id) FROM users));
SELECT setval(pg_get_serial_sequence('households', 'id'),             (SELECT MAX(id) FROM households));
SELECT setval(pg_get_serial_sequence('beneficiaries', 'id'),          (SELECT MAX(id) FROM beneficiaries));
SELECT setval(pg_get_serial_sequence('health_assessments', 'id'),     (SELECT MAX(id) FROM health_assessments));
SELECT setval(pg_get_serial_sequence('maternal_records', 'id'),       (SELECT MAX(id) FROM maternal_records));
SELECT setval(pg_get_serial_sequence('child_records', 'id'),          (SELECT MAX(id) FROM child_records));
SELECT setval(pg_get_serial_sequence('vaccines', 'id'),               (SELECT MAX(id) FROM vaccines));
SELECT setval(pg_get_serial_sequence('immunization_schedules', 'id'), (SELECT MAX(id) FROM immunization_schedules));
SELECT setval(pg_get_serial_sequence('medicines', 'id'),              (SELECT MAX(id) FROM medicines));
SELECT setval(pg_get_serial_sequence('prescriptions', 'id'),          (SELECT MAX(id) FROM prescriptions));
SELECT setval(pg_get_serial_sequence('home_visits', 'id'),            (SELECT MAX(id) FROM home_visits));
SELECT setval(pg_get_serial_sequence('referrals', 'id'),              (SELECT MAX(id) FROM referrals));

COMMIT;
