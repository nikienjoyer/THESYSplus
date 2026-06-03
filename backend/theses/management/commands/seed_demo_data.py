"""Management command — seed realistic demo data for THESYS+ prototype defense.

Usage:
    python manage.py seed_demo_data                    # seed + generate embeddings
    python manage.py seed_demo_data --skip-embeddings  # seed without embeddings
    python manage.py seed_demo_data --regenerate-embeddings  # re-embed all demo theses
    python manage.py seed_demo_data --reset            # wipe demo data then re-seed

Dataset design:
    50 users  (35 students, 10 faculty, 5 admins)
    100 theses across 10 topic clusters

    Defense-oriented composition:
      70 normal theses  — broad realistic coverage
      20 semantically related theses — grouped into research sub-clusters
      10 intentionally similar titles — exercises Title Similarity feature

    Year distribution shaped to reveal topic-trend evolution in Trend Analysis:
      2020–2021: Inventory / POS / Management Systems dominant
      2022–2023: IoT / Monitoring / Embedded Systems dominant
      2024–2025: AI / Machine Learning / Data Analytics dominant

    Status: 80 approved, 15 pending_review, 5 rejected
    Program: ~40 BSIS, ~35 BSIT, ~25 BSCS
"""

from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus

DEMO_PASSWORD = 'ThesysDemo2026!'

# ── Stable email lists (deterministic for idempotency) ────────────────────
STUDENT_EMAILS = [f'2021{str(i).zfill(6)}@pampangastateu.edu.ph' for i in range(1, 36)]
FACULTY_EMAILS = [f'faculty{str(i).zfill(2)}@pampangastateu.edu.ph' for i in range(1, 11)]
ADMIN_EMAILS   = [f'admin{str(i).zfill(2)}@pampangastateu.edu.ph'   for i in range(1, 6)]
ALL_DEMO_EMAILS = set(STUDENT_EMAILS + FACULTY_EMAILS + ADMIN_EMAILS)

# ── Faculty name roster (10 faculty → advisers for theses) ───────────────
FACULTY_USERS = [
    {'email': FACULTY_EMAILS[0],  'first': 'Roberto',   'last': 'Reyes',      'title': 'Prof.'},
    {'email': FACULTY_EMAILS[1],  'first': 'Carmen',    'last': 'Villanueva', 'title': 'Dr.'},
    {'email': FACULTY_EMAILS[2],  'first': 'Luis',      'last': 'Mendoza',    'title': 'Engr.'},
    {'email': FACULTY_EMAILS[3],  'first': 'Miguel',    'last': 'Tan',        'title': 'Prof.'},
    {'email': FACULTY_EMAILS[4],  'first': 'Patricia',  'last': 'Ramos',      'title': 'Dr.'},
    {'email': FACULTY_EMAILS[5],  'first': 'Jose',      'last': 'Bautista',   'title': 'Prof.'},
    {'email': FACULTY_EMAILS[6],  'first': 'Christopher','last': 'Sy',        'title': 'Dr.'},
    {'email': FACULTY_EMAILS[7],  'first': 'Ana',       'last': 'Garcia',     'title': 'Prof.'},
    {'email': FACULTY_EMAILS[8],  'first': 'Ricardo',   'last': 'Santos',     'title': 'Dr.'},
    {'email': FACULTY_EMAILS[9],  'first': 'Elena',     'last': 'Cruz',       'title': 'Prof.'},
]

STUDENT_NAMES = [
    ('Dela Cruz', 'Juan', 'M.'),    ('Santos', 'Maria', 'L.'),
    ('Reyes', 'Pedro', 'A.'),       ('Garcia', 'Ana', 'B.'),
    ('Lopez', 'Carlos', 'D.'),      ('Mendoza', 'Luis', 'E.'),
    ('Torres', 'Rosa', 'F.'),       ('Villanueva', 'Carmen', 'P.'),
    ('Cruz', 'Antonio', 'R.'),      ('Tan', 'Miguel', 'S.'),
    ('Aquino', 'Bernadette', 'J.'), ('Ramos', 'Patricia', 'C.'),
    ('Sy', 'Christopher', 'D.'),    ('Cabrera', 'Maria', 'E.'),
    ('Lim', 'Joshua', 'F.'),        ('Park', 'Hannah', 'G.'),
    ('Bautista', 'Jose', 'H.'),     ('Mercado', 'Daniel', 'I.'),
    ('Yap', 'Sophia', 'J.'),        ('Navarro', 'Kim', 'L.'),
    ('Alarcon', 'Faith', 'M.'),     ('Buenaventura', 'Rico', 'N.'),
    ('Castillo', 'Lea', 'O.'),      ('Dizon', 'Mark', 'P.'),
    ('Espiritu', 'Nina', 'Q.'),     ('Flores', 'Jerome', 'R.'),
    ('Gutierrez', 'Pia', 'S.'),     ('Herrera', 'Arvin', 'T.'),
    ('Ignacio', 'Chesca', 'U.'),    ('Jacinto', 'Noel', 'V.'),
    ('Kalaw', 'Tricia', 'W.'),      ('Lacson', 'Eddie', 'X.'),
    ('Manalo', 'Grace', 'Y.'),      ('Nacpil', 'Ben', 'Z.'),
    ('Ocampo', 'Luz', 'A.'),
]

ADMIN_NAMES = [
    ('Admin', 'Alice', 'A.'),
    ('Admin', 'Bruno', 'B.'),
    ('Admin', 'Clara', 'C.'),
    ('Admin', 'Diego', 'D.'),
    ('Admin', 'Eva',   'E.'),
]

# ── Helper: adviser display name ──────────────────────────────────────────
def _adviser(idx: int) -> str:
    f = FACULTY_USERS[idx % len(FACULTY_USERS)]
    return f"{f['title']} {f['last']}, {f['first']}"


# ── Helper: faculty email for uploaded_by/reviewed_by ────────────────────
def _fac_email(idx: int) -> str:
    return FACULTY_USERS[idx % len(FACULTY_USERS)]['email']


# ── Helper: student email for uploaded_by ────────────────────────────────
def _stu_email(idx: int) -> str:
    return STUDENT_EMAILS[idx % len(STUDENT_EMAILS)]


def _authors(*idxs) -> list:
    result = []
    for i in idxs:
        n = STUDENT_NAMES[i % len(STUDENT_NAMES)]
        result.append(f'{n[0]}, {n[1]} {n[2]}')
    return result


# ═══════════════════════════════════════════════════════════════════════════
# THESIS DATA — 100 theses across 10 clusters
#
# Each entry:
#   title, abstract, authors (list of student name indices), keywords,
#   program, year, adviser_idx, uploaded_by_idx (student),
#   status  ('approved' | 'pending_review' | 'rejected')
#
# Composition:
#   70 normal  + 20 semantically related + 10 similar-title pairs
#   (marked with inline comments for traceability)
#
# Year pattern:
#   2020–2021 → Inventory/POS/Management heavy
#   2022–2023 → IoT/Monitoring/Embedded heavy
#   2024–2025 → AI/ML/Analytics heavy
# ═══════════════════════════════════════════════════════════════════════════

BSIS = Program.BSIS.value
BSIT = Program.BSIT.value
BSCS = Program.BSCS.value

AP = ThesisStatus.APPROVED.value
PR = ThesisStatus.PENDING_REVIEW.value
RJ = ThesisStatus.REJECTED.value

THESES_DATA = [

    # ── CLUSTER 1: Attendance and Monitoring Systems (12 theses) ─────────────
    # 3 intentionally similar titles for Title Similarity demo
    {
        'title': 'RFID-Based Attendance Monitoring System for College Students',
        'abstract': 'This study developed a radio-frequency identification attendance monitoring system for college-level classrooms at PampangaStateU CCS. RFID card readers installed at classroom entry points log student attendance automatically, eliminating manual roll calls. The system integrates with a web dashboard that faculty can access in real time. Evaluation results show a 99.1% read accuracy rate and a reduction in administrative overhead by approximately 40%.',
        'authors': _authors(0, 1),
        'keywords': ['RFID', 'attendance', 'monitoring', 'web system', 'automation'],
        'program': BSIT, 'year': 2021, 'adviser_idx': 0, 'uploader_idx': 0, 'status': AP,
    },
    {
        'title': 'RFID Attendance Monitoring System for CCS Department',  # similar title
        'abstract': 'A department-wide implementation of RFID-based attendance tracking covering all CCS laboratories and lecture halls. Student ID cards are used as RFID tokens. An administrative panel allows staff to generate attendance reports per subject and export them to Excel. The system logged over 12,000 attendance records during a one-semester pilot with no reported false reads.',
        'authors': _authors(2, 3),
        'keywords': ['RFID', 'attendance', 'monitoring', 'CCS', 'student records'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 0, 'uploader_idx': 2, 'status': AP,
    },
    {
        'title': 'Student Attendance Tracking Using RFID Technology',  # similar title
        'abstract': 'An RFID-driven student attendance tracking platform that supports multiple simultaneous readers across campus buildings. The backend uses Django REST Framework and PostgreSQL for reliable record storage. A mobile companion app lets students view their own attendance history. Tests conducted across three buildings showed consistent sub-second registration latency.',
        'authors': _authors(4, 5),
        'keywords': ['RFID', 'attendance tracking', 'student monitoring', 'Django', 'mobile'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 0, 'uploader_idx': 4, 'status': AP,
    },
    {
        'title': 'Facial Recognition Attendance System Using Deep Learning',
        'abstract': 'Employs MTCNN face detection and FaceNet embeddings to identify students as they enter classrooms. The system achieves 97.2% recognition accuracy under controlled indoor lighting. A live dashboard notifies instructors of unrecognized faces for manual verification. The model was fine-tuned on a dataset of 3,200 PampangaStateU CCS student photos.',
        'authors': _authors(6, 7),
        'keywords': ['facial recognition', 'attendance', 'deep learning', 'MTCNN', 'FaceNet'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 1, 'uploader_idx': 6, 'status': AP,
    },
    {
        'title': 'QR Code-Based Classroom Attendance System with Analytics Dashboard',
        'abstract': 'Students scan a time-limited QR code displayed by the instructor to mark attendance. The QR token refreshes every 60 seconds to prevent screenshot reuse. An analytics dashboard aggregates attendance rates per class, subject, and semester, and flags students below the 80% attendance threshold automatically.',
        'authors': _authors(8, 9),
        'keywords': ['QR code', 'attendance', 'analytics', 'classroom', 'web system'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 2, 'uploader_idx': 8, 'status': AP,
    },
    {
        'title': 'Biometric Fingerprint Attendance Management System',
        'abstract': 'Integrates commercial fingerprint scanners with a centralized attendance database via a USB HID driver wrapper. Faculty can pull attendance reports across departments from a single admin interface. The system handled a load test of 500 concurrent student enrollments without data loss. Fingerprint templates are stored using ISO/IEC 19794-2 format for interoperability.',
        'authors': _authors(10, 11),
        'keywords': ['biometric', 'fingerprint', 'attendance', 'management', 'security'],
        'program': BSIT, 'year': 2021, 'adviser_idx': 3, 'uploader_idx': 10, 'status': AP,
    },
    {
        'title': 'Automated Employee Attendance and Payroll Integration System',
        'abstract': 'A combined RFID-and-PIN attendance system for university support staff that feeds time-log data directly into the payroll computation module. Overtime and undertime are computed using configurable shift rules. The system was piloted with 120 non-teaching staff over one quarter and correctly computed payroll for all pay periods with no manual corrections needed.',
        'authors': _authors(12, 13),
        'keywords': ['attendance', 'payroll', 'RFID', 'automation', 'human resources'],
        'program': BSIS, 'year': 2020, 'adviser_idx': 4, 'uploader_idx': 12, 'status': AP,
    },
    {
        'title': 'GPS-Based Field Personnel Monitoring System for Utility Workers',
        'abstract': 'A mobile app paired with a backend tracking service that records the real-time GPS coordinates of field utility workers dispatched from the university facilities office. Supervisors can view live locations on an OpenStreetMap-based dashboard. The system alerts supervisors when a worker deviates from an assigned route by more than 200 meters.',
        'authors': _authors(14, 15),
        'keywords': ['GPS', 'monitoring', 'field tracking', 'mobile', 'location services'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 5, 'uploader_idx': 14, 'status': AP,
    },
    {
        'title': 'Smart Campus Vehicle Entry Monitoring with License Plate Recognition',
        'abstract': 'Uses OpenCV and a custom-trained YOLOv8 model to extract license plate text from IP camera feeds at the campus entrance. Recognized plates are matched against an authorized vehicle registry. Unrecognized plates trigger an alert to the security booth. The system processed 1,400 vehicle entries during a two-week evaluation period with 94.6% plate-read accuracy.',
        'authors': _authors(16, 17),
        'keywords': ['license plate recognition', 'YOLO', 'monitoring', 'computer vision', 'security'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 6, 'uploader_idx': 16, 'status': AP,
    },
    {
        'title': 'Indoor Location Tracking System Using Bluetooth Low Energy Beacons',
        'abstract': 'Deploys BLE beacons in campus corridors to triangulate student device positions for indoor navigation assistance. A Flutter app guides visitors to classrooms, offices, and laboratories using a campus floor plan overlay. Positioning accuracy in corridor tests averaged 2.8 meters, sufficient for room-level navigation.',
        'authors': _authors(18, 19),
        'keywords': ['BLE', 'indoor tracking', 'Bluetooth', 'navigation', 'Flutter'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 7, 'uploader_idx': 18, 'status': AP,
    },
    {
        'title': 'Remote Laboratory Equipment Monitoring Using IoT Sensors',
        'abstract': 'Raspberry Pi units installed in CCS laboratories continuously stream temperature, humidity, and equipment power-draw data to an MQTT broker. A Node-RED dashboard aggregates readings and sends email alerts when values breach acceptable ranges. The pilot covered eight laboratory rooms and detected three equipment overheat events in the first month.',
        'authors': _authors(20, 21),
        'keywords': ['IoT', 'monitoring', 'Raspberry Pi', 'MQTT', 'laboratory'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 2, 'uploader_idx': 20, 'status': AP,
    },
    {
        'title': 'Student Performance Monitoring Dashboard for Academic Advisers',
        'abstract': 'Aggregates grades, attendance, and extracurricular data from the registrar system into a single-pane dashboard for academic advisers. Trend lines flag students at risk of failing based on a logistic regression model trained on five years of historical records. Advisers reported a 30% reduction in time spent preparing advising materials in a usability trial.',
        'authors': _authors(22, 23),
        'keywords': ['monitoring', 'dashboard', 'student performance', 'academic advising', 'analytics'],
        'program': BSIS, 'year': 2024, 'adviser_idx': 8, 'uploader_idx': 22, 'status': PR,
    },

    # ── CLUSTER 2: Inventory and POS Systems (12 theses) ─────────────────────
    # 3 intentionally similar titles for Title Similarity demo
    {
        'title': 'Web-Based Inventory Management System for Small Retail Businesses',
        'abstract': 'A PHP Laravel and Vue.js inventory system tailored for small retail stores, enabling real-time stock tracking, reorder alerts, and supplier management. An integrated ARIMA demand-forecasting module predicts monthly reorder quantities. Three pilot stores in San Fernando reduced stockout incidents by 38% within the first quarter of deployment.',
        'authors': _authors(24, 25),
        'keywords': ['inventory', 'web system', 'retail', 'Laravel', 'stock management'],
        'program': BSIS, 'year': 2020, 'adviser_idx': 3, 'uploader_idx': 24, 'status': AP,
    },
    {
        'title': 'Inventory Monitoring and Stock Management System',  # similar title
        'abstract': 'A Django-powered stock control platform for medium-sized enterprises featuring barcode scanning, low-stock notifications, and supplier purchase order generation. The system supports multi-warehouse configurations and generates weekly inventory turnover reports. A six-month deployment at a university supply office reduced manual stock audits from weekly to monthly.',
        'authors': _authors(26, 27),
        'keywords': ['inventory', 'stock management', 'monitoring', 'barcode', 'Django'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 3, 'uploader_idx': 26, 'status': AP,
    },
    {
        'title': 'Inventory Tracking System for Small Retail Businesses',  # similar title
        'abstract': 'An Android-first inventory tracking application for sari-sari store operators in Pampanga. Owners scan barcodes or enter items manually to maintain a live stock ledger. The app works offline and syncs with a Firebase Firestore backend when connectivity is restored. Field testing with 15 store owners showed an average 45-minute weekly time saving on inventory counts.',
        'authors': _authors(28, 29),
        'keywords': ['inventory tracking', 'retail', 'Android', 'Firebase', 'offline'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 9, 'uploader_idx': 28, 'status': AP,
    },
    {
        'title': 'Point-of-Sale System with Sales Analytics for Cafeteria Management',
        'abstract': 'A touchscreen POS terminal built with Electron.js and SQLite for the university cafeteria. Cashiers process orders, apply discounts, and print receipts within a three-tap workflow. A management dashboard displays daily revenue, top-selling items, and hourly transaction volume. The system replaced manual cash registers and reduced billing errors by 92%.',
        'authors': _authors(30, 31),
        'keywords': ['POS', 'sales analytics', 'cafeteria', 'Electron', 'retail'],
        'program': BSIS, 'year': 2020, 'adviser_idx': 5, 'uploader_idx': 30, 'status': AP,
    },
    {
        'title': 'Integrated Point-of-Sale and Inventory System for University Bookstore',
        'abstract': 'Combines point-of-sale transaction processing with real-time inventory deduction for the PampangaStateU bookstore. Each completed sale automatically adjusts stock levels and triggers reorder flags when items fall below minimum quantities. End-of-day reconciliation reports are generated automatically and emailed to the bookstore manager.',
        'authors': _authors(32, 33),
        'keywords': ['POS', 'inventory', 'bookstore', 'web system', 'automation'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 4, 'uploader_idx': 32, 'status': AP,
    },
    {
        'title': 'Canteen Order Management System with Queue Display',
        'abstract': 'A web-based order queuing system for the university canteen that displays live order status on a TV-mounted screen. Students place orders from any browser; kitchen staff mark items as ready; the display board shows order numbers being served. Average customer wait time dropped from 12 minutes to 7 minutes during the pilot semester.',
        'authors': _authors(0, 34),
        'keywords': ['order management', 'queue', 'canteen', 'web system', 'real-time'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 9, 'uploader_idx': 0, 'status': AP,
    },
    {
        'title': 'Asset Management System for University Laboratory Equipment',
        'abstract': 'A QR-code-based asset tracking system for university laboratories covering acquisition, assignment, maintenance scheduling, and disposal workflows. Equipment records include photos, serial numbers, and depreciation schedules. Audit compliance reports are generated on demand. The system currently manages over 2,300 asset records across six CCS laboratories.',
        'authors': _authors(1, 2),
        'keywords': ['asset management', 'QR code', 'laboratory', 'web system', 'tracking'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 0, 'uploader_idx': 1, 'status': AP,
    },
    {
        'title': 'Supply Chain Management System for University Procurement',
        'abstract': 'A web application that digitizes the end-to-end procurement cycle from purchase request to delivery confirmation. Requestors submit forms online; approvers follow a configurable multi-level workflow; purchasing staff issue digital purchase orders to suppliers. The system reduced average procurement cycle time from 18 days to 9 days in the first year of operation.',
        'authors': _authors(3, 4),
        'keywords': ['supply chain', 'procurement', 'web system', 'workflow', 'management'],
        'program': BSIS, 'year': 2020, 'adviser_idx': 8, 'uploader_idx': 3, 'status': AP,
    },
    {
        'title': 'Pharmacy Inventory Management System with Expiry Date Monitoring',
        'abstract': 'A Django REST Framework and React inventory system for a community pharmacy that flags items nearing expiry and generates batch-recall lists. Near-expiry items within 30 days are highlighted in the dashboard. Integration with the POS module ensures that dispensed items are immediately deducted from stock. The clinic pharmacy reduced expired-item write-offs by 61% in the first six months.',
        'authors': _authors(5, 6),
        'keywords': ['pharmacy', 'inventory', 'expiry monitoring', 'Django', 'healthcare'],
        'program': BSIS, 'year': 2023, 'adviser_idx': 4, 'uploader_idx': 5, 'status': AP,
    },
    {
        'title': 'Rental Management System for University Facilities',
        'abstract': 'An online facility reservation and billing system for university venues including auditoriums, function halls, and sports courts. Organizations submit rental requests with event details; administrators approve or deny with remarks; invoices are generated automatically. Scheduling conflicts are prevented by a calendar-based availability engine.',
        'authors': _authors(7, 8),
        'keywords': ['rental', 'facilities management', 'reservation', 'web system', 'billing'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 5, 'uploader_idx': 7, 'status': AP,
    },
    {
        'title': 'Construction Materials Inventory System with Cost Tracking',
        'abstract': 'Tracks construction materials from delivery receipt to site consumption for a local government infrastructure project. Each material batch is logged with supplier invoices and unit costs, enabling real-time budget utilization reports. Wastage rates are calculated per project phase and highlighted when they exceed configurable tolerance thresholds.',
        'authors': _authors(9, 10),
        'keywords': ['inventory', 'construction', 'cost tracking', 'web system', 'government'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 9, 'uploader_idx': 9, 'status': AP,
    },
    {
        'title': 'Multi-Branch Inventory Synchronization System Using REST APIs',
        'abstract': 'A centralized inventory hub that synchronizes stock levels across multiple retail branch databases in near-real time using RESTful APIs. Branch managers push stock adjustments to the hub; the hub rebroadcasts reconciled totals to all branches within 15 seconds. A conflict-resolution algorithm handles simultaneous edits using timestamp-based last-write-wins logic.',
        'authors': _authors(11, 12),
        'keywords': ['inventory', 'REST API', 'synchronization', 'multi-branch', 'retail'],
        'program': BSIS, 'year': 2023, 'adviser_idx': 3, 'uploader_idx': 11, 'status': PR,
    },

    # ── CLUSTER 3: Learning Management / Educational Technology (11 theses) ──
    {
        'title': 'Django-Based Learning Management System for CCS Computing Courses',
        'abstract': 'A feature-complete LMS built with Django and React tailored for programming and networking courses at PampangaStateU CCS. The platform supports auto-graded coding challenges via a sandboxed Judge0 backend, peer review assignments, and BigBlueButton video conferencing integration. Adopted by four CCS subjects with 340 active learners in the first semester of deployment.',
        'authors': _authors(13, 14),
        'keywords': ['LMS', 'e-learning', 'Django', 'educational technology', 'web system'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 1, 'uploader_idx': 13, 'status': AP,
    },
    {
        'title': 'Adaptive E-Learning Platform with Personalized Learning Paths',
        'abstract': 'An adaptive learning system that uses item response theory to estimate student knowledge levels and dynamically adjusts the sequence of learning modules. When a student scores below threshold on a concept quiz, the platform routes them to prerequisite review materials before advancing. A 10-week trial across two programming subjects showed a 19% improvement in final exam scores versus the control group.',
        'authors': _authors(15, 16),
        'keywords': ['adaptive learning', 'e-learning', 'personalization', 'IRT', 'educational technology'],
        'program': BSIS, 'year': 2024, 'adviser_idx': 5, 'uploader_idx': 15, 'status': AP,
    },
    {
        'title': 'Gamification Framework for Introductory Programming Courses',
        'abstract': 'Introduces experience points, achievement badges, leaderboards, and daily coding challenges into an existing LMS to improve engagement in CS1 Python courses. Students who opted into the gamified interface submitted 27% more optional practice problems than the control group. Badge criteria were designed with faculty to align with course learning outcomes rather than superficial metrics.',
        'authors': _authors(17, 18),
        'keywords': ['gamification', 'e-learning', 'programming', 'engagement', 'educational technology'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 6, 'uploader_idx': 17, 'status': AP,
    },
    {
        'title': 'Automated Quiz Generation System Using Natural Language Processing',
        'abstract': 'Generates multiple-choice questions automatically from uploaded lecture PDFs using a T5-based question-generation model. Faculty upload a document; the system returns candidate questions with distractor options ranked by a quality classifier. In a blind faculty evaluation, 71% of generated questions were rated as acceptable for use without modification.',
        'authors': _authors(19, 20),
        'keywords': ['NLP', 'quiz generation', 'T5', 'educational technology', 'automation'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 19, 'status': AP,
    },
    {
        'title': 'Flipped Classroom Support System with Video Annotation Tools',
        'abstract': 'A web application that embeds time-stamped annotation and discussion threads directly on pre-recorded lecture videos. Students can flag confusing segments before class; instructors see an aggregated heat map of confusing timestamps to prioritize in-person discussion. Pilot feedback from 120 students indicated a 4.2/5.0 satisfaction rating for the annotation feature.',
        'authors': _authors(21, 22),
        'keywords': ['flipped classroom', 'video', 'annotation', 'e-learning', 'web system'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 8, 'uploader_idx': 21, 'status': AP,
    },
    {
        'title': 'Mobile-Based Flashcard Application with Spaced Repetition for Computer Science Students',
        'abstract': 'A React Native flashcard app that implements the SuperMemo SM-2 spaced repetition algorithm to schedule card reviews at optimal intervals. Students can create shared decks for programming concepts, data structures, and networking terms. Analytics show per-deck retention rates over time. Daily active users averaged 68 students during the exam season pilot.',
        'authors': _authors(23, 24),
        'keywords': ['mobile', 'flashcard', 'spaced repetition', 'educational technology', 'React Native'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 7, 'uploader_idx': 23, 'status': AP,
    },
    {
        'title': 'Online Examination System with Randomized Question Pools and Proctoring',
        'abstract': 'A secure online examination platform that draws randomized question sets from categorized item banks to minimize inter-student answer sharing. Tab-switching detection and periodic webcam snapshots are used as lightweight proctoring signals. Faculty can configure time limits, randomization settings, and automatic grading rubrics per exam.',
        'authors': _authors(25, 26),
        'keywords': ['online examination', 'proctoring', 'randomization', 'web system', 'education'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 9, 'uploader_idx': 25, 'status': AP,
    },
    {
        'title': 'Curriculum Mapping and Outcome-Based Education Tracking System',
        'abstract': 'Maps course learning outcomes to program outcomes and professional standards (CHED CMO) in a visual web interface. Faculty tag assessment activities to outcomes; the system aggregates performance data to produce program-level attainment reports required for accreditation. Department chairs can drill down from program-level charts to individual course and student records.',
        'authors': _authors(27, 28),
        'keywords': ['curriculum', 'OBE', 'outcome-based education', 'accreditation', 'web system'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 0, 'uploader_idx': 27, 'status': AP,
    },
    {
        'title': 'Virtual Laboratory Simulation Platform for Networking Experiments',
        'abstract': 'A browser-based network simulation environment where students configure and test virtual routers, switches, and end hosts without physical Cisco equipment. GNS3 topologies are pre-loaded per lab activity; student configurations are auto-graded by comparing routing tables and ping reachability against expected solutions. Used by 180 CCNA students in two semesters.',
        'authors': _authors(29, 30),
        'keywords': ['virtual lab', 'networking', 'simulation', 'GNS3', 'educational technology'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 2, 'uploader_idx': 29, 'status': AP,
    },
    {
        'title': 'Peer Assessment System for Collaborative Software Projects',
        'abstract': 'Facilitates structured peer evaluation of team roles, code contributions, and communication skills in software engineering capstone courses. Students complete calibrated rubrics anonymously; a weighted aggregation algorithm detects outlier raters and adjusts their scores. Faculty use the data to assign individual grades within group projects, reducing free-riding complaints by 55%.',
        'authors': _authors(31, 32),
        'keywords': ['peer assessment', 'collaborative learning', 'capstone', 'web system', 'education'],
        'program': BSIS, 'year': 2024, 'adviser_idx': 4, 'uploader_idx': 31, 'status': AP,
    },
    {
        'title': 'Digital Classroom Participation Tracker for Blended Learning',
        'abstract': 'Tracks verbal and digital participation across both physical and online learning environments. In physical classes, the instructor marks participation via a tablet app; in online sessions, the system counts forum posts, chat messages, and poll responses. Aggregated participation scores are visible to students in real time through a personal dashboard.',
        'authors': _authors(33, 34),
        'keywords': ['participation tracking', 'blended learning', 'dashboard', 'educational technology', 'classroom'],
        'program': BSIS, 'year': 2024, 'adviser_idx': 3, 'uploader_idx': 33, 'status': PR,
    },

    # ── CLUSTER 4: AI and Machine Learning (10 theses) ───────────────────────
    # 3 intentionally similar titles + semantic sub-cluster on student performance
    {
        'title': 'Student Performance Prediction Using Machine Learning',  # similar title
        'abstract': 'Applies five supervised classification algorithms — decision tree, random forest, SVM, k-NN, and gradient boosting — to predict end-of-semester student performance using mid-term grades, attendance, and learning management system engagement features. Random forest achieved the best accuracy of 88.3% in a 5-fold cross-validation experiment on three years of CCS student records.',
        'authors': _authors(0, 1),
        'keywords': ['machine learning', 'student performance', 'prediction', 'classification', 'random forest'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 1, 'uploader_idx': 0, 'status': AP,
    },
    {
        'title': 'Machine Learning-Based Academic Performance Predictor',  # similar title
        'abstract': 'Builds a gradient boosting regressor to predict final GPA from first-year course grades, demographic data, and extracurricular participation records. Feature importance analysis identified first-year math grades as the strongest predictor. The model was validated on 1,800 student records from five graduating batches and achieved an RMSE of 0.31 GPA points.',
        'authors': _authors(2, 3),
        'keywords': ['machine learning', 'academic performance', 'prediction', 'GPA', 'gradient boosting'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 2, 'status': AP,
    },
    {
        'title': 'AI-Powered Student Performance Analysis System',  # similar title
        'abstract': 'An end-to-end analytics platform that ingests real-time grades, attendance, and behavioral signals from the university LMS, applies a neural network classifier, and surfaces at-risk student alerts to academic advisers. The dashboard visualizes performance trajectories and cluster profiles, enabling early intervention two weeks earlier than conventional grade-book reviews.',
        'authors': _authors(4, 5),
        'keywords': ['artificial intelligence', 'student performance', 'analytics', 'neural network', 'at-risk'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 6, 'uploader_idx': 4, 'status': AP,
    },
    # Semantic sub-cluster: recommendation systems (different wording, same concept)
    {
        'title': 'Student Course Recommendation Platform Using Collaborative Filtering',
        'abstract': 'A web-based course recommendation engine that leverages collaborative filtering to suggest elective subjects to students based on the enrollment history and academic outcomes of similar peers. Matrix factorization via SVD++ models latent student-subject affinity. Offline evaluation on five years of enrollment data achieved a precision@5 of 0.74 and recall@5 of 0.68.',
        'authors': _authors(6, 7),
        'keywords': ['recommendation', 'collaborative filtering', 'machine learning', 'course', 'SVD'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 6, 'status': AP,
    },
    {
        'title': 'Intelligent Academic Recommendation Engine for Elective Selection',
        'abstract': 'Combines content-based filtering of course syllabi with collaborative user signals to produce ranked elective recommendations for third-year BS Computer Science students. TF-IDF vectors of course descriptions are clustered to find semantically related subjects, which are then reranked using a student similarity score. A/B test showed a 22% increase in satisfaction with elective choices.',
        'authors': _authors(8, 9),
        'keywords': ['recommendation system', 'content-based filtering', 'TF-IDF', 'academic', 'NLP'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 6, 'uploader_idx': 8, 'status': AP,
    },
    {
        'title': 'Machine Learning-Based Subject Recommendation System for College Students',
        'abstract': 'A hybrid recommender combining item-based collaborative filtering with a course prerequisite graph to prevent students from being recommended subjects they are not yet qualified for. The prerequisite constraint layer reduced logically invalid recommendations to zero while preserving recommendation diversity. Validated with 300 student survey responses confirming 81% agreement with suggestions.',
        'authors': _authors(10, 11),
        'keywords': ['recommendation system', 'machine learning', 'subject', 'collaborative filtering', 'college'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 8, 'uploader_idx': 10, 'status': AP,
    },
    {
        'title': 'Natural Language Processing for Automated Student Feedback Classification',
        'abstract': 'Fine-tunes a multilingual BERT model on 8,500 labeled Filipino-English student feedback survey responses to classify sentiment and topic categories automatically. The classifier reduces manual survey analysis time from three staff-days to under one hour per semester. Topic categories include teaching quality, facilities, curriculum relevance, and administrative services.',
        'authors': _authors(12, 13),
        'keywords': ['NLP', 'BERT', 'sentiment analysis', 'feedback classification', 'Filipino'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 12, 'status': AP,
    },
    {
        'title': 'Transfer Learning for Plant Disease Detection in Local Crops',
        'abstract': 'Fine-tunes EfficientNet-B2 on a 4,200-image dataset of Pampanga-region crop diseases including rice blast, cassava mosaic, and corn leaf blight. The mobile TFLite model achieves 93.7% top-1 accuracy on held-out test images and runs at 15 FPS on a mid-range Android device. A companion web dashboard lets agricultural extension workers upload batch photos for disease screening.',
        'authors': _authors(14, 15),
        'keywords': ['transfer learning', 'EfficientNet', 'plant disease', 'agriculture', 'mobile AI'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 6, 'uploader_idx': 14, 'status': AP,
    },
    {
        'title': 'Convolutional Neural Network for Handwritten Baybayin Script Recognition',
        'abstract': 'Trains a four-layer CNN on 6,000 handwritten Baybayin characters scanned from student worksheets to enable digital archiving of pre-colonial Philippine scripts. The model achieves 96.2% character-level accuracy. An OCR pipeline converts scanned documents to Unicode representation, and a web viewer renders the transliterated text alongside the original scan.',
        'authors': _authors(16, 17),
        'keywords': ['CNN', 'OCR', 'Baybayin', 'handwritten recognition', 'cultural heritage'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 6, 'uploader_idx': 16, 'status': AP,
    },
    {
        'title': 'Anomaly Detection in Network Traffic Using Autoencoder Neural Networks',
        'abstract': 'Deploys an autoencoder trained on benign campus network traffic to flag anomalous packets indicative of port scans, DDoS patterns, and data exfiltration. Reconstruction error above a tuned threshold triggers an alert logged to a SIEM-compatible event stream. On the CICIDS2017 benchmark dataset, the model achieves an F1 score of 0.91 for anomaly detection.',
        'authors': _authors(18, 19),
        'keywords': ['anomaly detection', 'neural network', 'network security', 'autoencoder', 'machine learning'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 8, 'uploader_idx': 18, 'status': PR,
    },

    # ── CLUSTER 5: IoT and Embedded Systems (10 theses) ──────────────────────
    {
        'title': 'ESP32-Based Greenhouse Environmental Monitoring System',
        'abstract': 'An ESP32 microcontroller array monitors soil moisture, ambient temperature, humidity, and light intensity across a 500 sqm greenhouse. Sensor readings are published via MQTT to a cloud broker and visualized on a Node-RED dashboard. Automated irrigation actuators trigger when soil moisture falls below configurable thresholds, reducing daily water consumption by 31%.',
        'authors': _authors(20, 21),
        'keywords': ['IoT', 'ESP32', 'MQTT', 'greenhouse', 'sensors'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 2, 'uploader_idx': 20, 'status': AP,
    },
    {
        'title': 'Smart Street Lighting System with Adaptive Brightness Control',
        'abstract': 'NodeMCU-based smart streetlight controllers adjust brightness based on ambient light sensor readings and a PIR motion detector. Lights dim to 30% when no motion is detected and return to full brightness within 200 ms of detecting pedestrians. A central dashboard tracks energy consumption per lamp post and flags units needing maintenance based on abnormal current draws.',
        'authors': _authors(22, 23),
        'keywords': ['IoT', 'smart lighting', 'NodeMCU', 'energy efficiency', 'automation'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 2, 'uploader_idx': 22, 'status': AP,
    },
    {
        'title': 'Flood Early Warning System Using Ultrasonic Water Level Sensors',
        'abstract': 'Ultrasonic sensors installed at five creek monitoring points in flood-prone Pampanga municipalities transmit water level readings every 30 seconds via LoRa WAN to a central server. When levels exceed danger thresholds, SMS alerts are dispatched to registered residents and LGU officials. The system issued 14 accurate pre-flood alerts during the 2023 rainy season with zero false alarms.',
        'authors': _authors(24, 25),
        'keywords': ['IoT', 'flood monitoring', 'LoRa', 'early warning', 'sensors'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 7, 'uploader_idx': 24, 'status': AP,
    },
    {
        'title': 'Automated Aquaponics Monitoring and Control System',
        'abstract': 'Monitors pH, dissolved oxygen, water temperature, and turbidity in an aquaponics system using a Raspberry Pi 4 and analog sensor array. Actuators control water pumps, aerators, and grow lights. A machine learning regression model predicts fish harvest weight from 30-day sensor history. The system maintained optimal water parameters 94% of the time over a six-month operational period.',
        'authors': _authors(26, 27),
        'keywords': ['IoT', 'aquaponics', 'Raspberry Pi', 'automation', 'sensors'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 2, 'uploader_idx': 26, 'status': AP,
    },
    {
        'title': 'Smart Waste Segregation Bin Using Computer Vision and Servo Motors',
        'abstract': 'A Raspberry Pi-powered waste bin uses a camera and a MobileNetV2 classifier to identify whether deposited waste is biodegradable, recyclable, or residual, then automatically routes it to the correct compartment via servo-actuated flaps. Trained on 2,800 locally collected waste images, the classifier achieves 89.4% accuracy on held-out samples.',
        'authors': _authors(28, 29),
        'keywords': ['IoT', 'computer vision', 'waste management', 'MobileNet', 'Raspberry Pi'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 7, 'uploader_idx': 28, 'status': AP,
    },
    {
        'title': 'Home Automation System Using Voice Commands and Raspberry Pi',
        'abstract': 'Integrates a wake-word detection model with a home automation hub to control lights, fans, and door locks via natural language voice commands spoken in Filipino and English. The Porcupine wake-word engine runs locally for privacy; device commands are dispatched via MQTT. A companion mobile app provides manual override and scheduling capabilities.',
        'authors': _authors(30, 31),
        'keywords': ['IoT', 'home automation', 'voice control', 'Raspberry Pi', 'MQTT'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 5, 'uploader_idx': 30, 'status': AP,
    },
    {
        'title': 'Soil Fertility Analysis Using IoT Sensors and Machine Learning',
        'abstract': 'An IoT probe measures soil NPK (nitrogen, phosphorus, potassium) levels, pH, and moisture. Readings are transmitted to a cloud API that runs a random forest regressor to classify soil fertility and recommend fertilizer types and dosages for common Pampanga crops. Farmers receive recommendations via an SMS gateway without needing smartphone access.',
        'authors': _authors(32, 33),
        'keywords': ['IoT', 'soil analysis', 'agriculture', 'machine learning', 'sensors'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 7, 'uploader_idx': 32, 'status': AP,
    },
    {
        'title': 'Smart Parking Management System Using Ultrasonic Sensors and IoT',
        'abstract': 'Ultrasonic sensors mounted above each parking bay detect occupancy and stream status to an MQTT broker. A React web dashboard and a mobile app display a live campus parking map with color-coded bay availability. The system guides drivers to the nearest free bay, reducing average parking search time from 8 minutes to 2 minutes during peak hours.',
        'authors': _authors(34, 0),
        'keywords': ['IoT', 'parking', 'ultrasonic sensors', 'MQTT', 'smart campus'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 3, 'uploader_idx': 34, 'status': AP,
    },
    {
        'title': 'Air Quality Monitoring Network for Urban Barangays',
        'abstract': 'A network of 12 low-cost MQ-series air quality sensors deployed across urban barangays in Angeles City measures PM2.5, CO, NO2, and ozone concentrations. Data is aggregated every five minutes and displayed on a public web portal with health advisory color codes. Readings were cross-validated against a reference-grade sensor and showed a correlation coefficient of 0.87.',
        'authors': _authors(1, 2),
        'keywords': ['IoT', 'air quality', 'environmental monitoring', 'sensors', 'public health'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 2, 'uploader_idx': 1, 'status': AP,
    },
    {
        'title': 'Wearable Fall Detection Device for Elderly Patients Using Accelerometers',
        'abstract': 'A wrist-worn device with a three-axis accelerometer and gyroscope detects falls using a threshold-based algorithm combined with a support vector machine classifier. Detected falls trigger a BLE alert to a companion app, which automatically contacts a registered caregiver. In a simulated fall study with 20 participants, the device achieved 96% sensitivity and 94% specificity.',
        'authors': _authors(3, 4),
        'keywords': ['wearable', 'IoT', 'fall detection', 'accelerometer', 'elderly care'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 4, 'uploader_idx': 3, 'status': PR,
    },

    # ── CLUSTER 6: Health Information Systems (10 theses) ────────────────────
    {
        'title': 'Electronic Health Records System for University Clinic',
        'abstract': 'A Django REST and React EHR system designed for the PampangaStateU Health Services Unit. Physicians record SOAP-format consultation notes, prescriptions, and laboratory results. Patient history is accessible across clinic visits with role-based access controls restricting sensitive records to licensed clinicians. The system replaced paper-based records for 6,400 active student patients.',
        'authors': _authors(5, 6),
        'keywords': ['EHR', 'health records', 'clinic', 'web system', 'healthcare'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 4, 'uploader_idx': 5, 'status': AP,
    },
    {
        'title': 'Telemedicine Consultation Platform for Remote Patients',
        'abstract': 'A WebRTC-based telemedicine platform enabling video consultations between patients and physicians in geographically underserved Pampanga municipalities. Physicians can annotate uploaded lab images during the call. Prescription records are stored in the patient EHR and can be transmitted to partner pharmacies digitally. Over 1,200 consultations were completed in the first four months of operation.',
        'authors': _authors(7, 8),
        'keywords': ['telemedicine', 'WebRTC', 'healthcare', 'video consultation', 'web system'],
        'program': BSIS, 'year': 2023, 'adviser_idx': 4, 'uploader_idx': 7, 'status': AP,
    },
    {
        'title': 'Mobile Health Monitoring App for Hypertension Management',
        'abstract': 'A Flutter application pairs with a Bluetooth blood pressure cuff to log readings, compute seven-day rolling trends, and send threshold alerts to a designated physician. Data is encrypted at rest using AES-256 and in transit via TLS 1.3. In a 90-day pilot with 45 hypertensive patients, medication adherence improved by 24% due to daily reminder notifications.',
        'authors': _authors(9, 10),
        'keywords': ['mobile health', 'hypertension', 'Flutter', 'Bluetooth', 'wearable'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 4, 'uploader_idx': 9, 'status': AP,
    },
    {
        'title': 'Dengue Case Surveillance and Mapping System for Local Government',
        'abstract': 'Aggregates dengue case reports from barangay health centers into a GIS-enabled dashboard that plots case clusters on an interactive map using Leaflet.js. A heat map layer identifies high-risk areas by case density, supporting targeted fumigation scheduling. The system integrated data from 32 barangay health centers and was used by the Pampanga Provincial Health Office.',
        'authors': _authors(11, 12),
        'keywords': ['disease surveillance', 'GIS', 'public health', 'dengue', 'dashboard'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 8, 'uploader_idx': 11, 'status': AP,
    },
    {
        'title': 'Automated Prescription Verification and Drug Interaction Checker',
        'abstract': 'A pharmacist-facing web tool that cross-checks prescribed drug combinations against a locally maintained drug interaction database before dispensing. Potential interactions are classified by severity (minor, moderate, major) and presented with clinical references. Integration with the clinic EHR allows pharmacists to view the prescribing physician notes without leaving the verification screen.',
        'authors': _authors(13, 14),
        'keywords': ['pharmacy', 'drug interaction', 'prescription', 'healthcare', 'web system'],
        'program': BSIS, 'year': 2023, 'adviser_idx': 4, 'uploader_idx': 13, 'status': AP,
    },
    {
        'title': 'Maternal Health Monitoring System for Rural Barangay Health Workers',
        'abstract': 'A Progressive Web App designed for offline-first use by barangay health workers conducting prenatal home visits in areas with intermittent connectivity. Workers record maternal weight, blood pressure, fundal height, and fetal heart rate on a mobile form; data syncs to the provincial health office server when a connection is available. Designed according to DOH maternal care guidelines.',
        'authors': _authors(15, 16),
        'keywords': ['maternal health', 'PWA', 'offline', 'barangay', 'healthcare'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 9, 'uploader_idx': 15, 'status': AP,
    },
    {
        'title': 'Computer-Aided Detection of Tuberculosis in Chest X-Ray Images',
        'abstract': 'Fine-tunes a DenseNet-121 model on the Montgomery County and Shenzhen chest X-ray datasets supplemented with 200 locally collected Philippine hospital images. The model detects TB-consistent infiltrates with 91.4% sensitivity and 88.7% specificity. A web interface allows radiologists to upload X-ray images and receive annotated heatmap overlays highlighting suspicious regions.',
        'authors': _authors(17, 18),
        'keywords': ['medical imaging', 'DenseNet', 'tuberculosis', 'deep learning', 'chest X-ray'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 6, 'uploader_idx': 17, 'status': AP,
    },
    {
        'title': 'Patient Queue Management System for Hospital Outpatient Department',
        'abstract': 'A token-based queue management system for the outpatient department that displays real-time estimated waiting times per service counter. Patients receive printed tokens or SMS notifications when their turn is approaching. The system reduced average patient waiting time from 47 minutes to 28 minutes across 15 service windows in a government hospital pilot.',
        'authors': _authors(19, 20),
        'keywords': ['queue management', 'hospital', 'patient flow', 'web system', 'SMS'],
        'program': BSIS, 'year': 2021, 'adviser_idx': 9, 'uploader_idx': 19, 'status': AP,
    },
    {
        'title': 'Nutrition Tracking and Dietary Assessment Mobile Application',
        'abstract': 'A React Native app that allows users to log meals using a local Philippine food nutrient database compiled from FNRI tables. A barcode scanner integrates with an open food database for packaged products. Daily nutrient summaries are compared against RENI (Recommended Energy and Nutrient Intake) targets. Tested with 60 PampangaStateU student volunteers over eight weeks.',
        'authors': _authors(21, 22),
        'keywords': ['nutrition', 'mobile', 'dietary assessment', 'React Native', 'health'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 4, 'uploader_idx': 21, 'status': PR,
    },
    {
        'title': 'Mental Health Self-Assessment Portal with Counselor Referral System',
        'abstract': 'A confidential web portal where students complete validated mental health screening tools (PHQ-9, GAD-7, and PSS) and receive immediate automated psychoeducation materials based on their scores. Students scoring in at-risk ranges are offered one-click referral to the university guidance counselor, who receives a notification with the anonymized screening summary.',
        'authors': _authors(23, 24),
        'keywords': ['mental health', 'screening', 'web system', 'counseling', 'student wellness'],
        'program': BSIS, 'year': 2025, 'adviser_idx': 8, 'uploader_idx': 23, 'status': PR,
    },

    # ── CLUSTER 7: Data Analytics and Dashboards (9 theses) ──────────────────
    {
        'title': 'Enrollment Trend Analysis Dashboard for Academic Planning',
        'abstract': 'Aggregates five years of PampangaStateU enrollment data by program, year level, and demographic attributes to produce interactive trend visualizations using D3.js. The dashboard forecasts next-year enrollment figures per program using a linear regression model and presents confidence intervals. Academic planning staff used the tool to justify a 15% increase in BSCS section offerings for AY 2025.',
        'authors': _authors(25, 26),
        'keywords': ['data analytics', 'dashboard', 'enrollment', 'trend analysis', 'D3.js'],
        'program': BSIS, 'year': 2024, 'adviser_idx': 8, 'uploader_idx': 25, 'status': AP,
    },
    {
        'title': 'Research Publication Analytics Tool for CCS Faculty',
        'abstract': 'Harvests publication metadata from ORCID and Scopus APIs to build a departmental research output dashboard. Faculty can view individual h-index trends, co-authorship network graphs, and citation counts. The tool identifies under-represented research topics by clustering title keywords with k-means and visualizing the gap between faculty output and CCS program research thrusts.',
        'authors': _authors(27, 28),
        'keywords': ['research analytics', 'Scopus', 'data visualization', 'faculty', 'publication'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 27, 'status': AP,
    },
    {
        'title': 'Sales Forecasting Dashboard for Agricultural Cooperatives',
        'abstract': 'Implements ARIMA and Facebook Prophet time-series models to forecast monthly crop sales for Pampanga agricultural cooperatives. The web dashboard allows cooperative managers to select crops and forecast horizons interactively. Back-tested on three years of cooperative sales data, Prophet outperformed ARIMA with a MAPE of 8.7% versus 13.2% for rice price forecasting.',
        'authors': _authors(29, 30),
        'keywords': ['forecasting', 'time series', 'Prophet', 'agriculture', 'data analytics'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 1, 'uploader_idx': 29, 'status': AP,
    },
    {
        'title': 'Power Consumption Analytics Platform for University Buildings',
        'abstract': 'Smart meters installed in five university buildings transmit hourly electricity consumption data to a central analytics database. A React dashboard displays consumption heatmaps per floor and identifies peak-load periods. An anomaly detection algorithm flags unusual consumption spikes for building management investigation. The platform identified three faulty HVAC units contributing to a 9% energy over-consumption.',
        'authors': _authors(31, 32),
        'keywords': ['data analytics', 'energy consumption', 'IoT', 'dashboard', 'anomaly detection'],
        'program': BSIS, 'year': 2023, 'adviser_idx': 5, 'uploader_idx': 31, 'status': AP,
    },
    {
        'title': 'Crime Pattern Analysis and Visualization System for Local Police',
        'abstract': 'Geocodes crime incident reports from the local police blotter and clusters events using DBSCAN to identify crime hotspots. An administrative dashboard plots incident density on a barangay-level choropleth map, enabling patrol route optimization. Temporal analysis reveals day-of-week and time-of-day patterns to support shift scheduling decisions.',
        'authors': _authors(33, 34),
        'keywords': ['data analytics', 'crime analysis', 'GIS', 'DBSCAN', 'visualization'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 6, 'uploader_idx': 33, 'status': AP,
    },
    {
        'title': 'Business Intelligence Dashboard for University Financial Reports',
        'abstract': 'Consolidates budget utilization, revenue, and expenditure data from the university accounting system into a Power BI-style interactive web dashboard built with Apache Superset. Finance officers drill down from university-level summaries to department-level line items. Automated monthly report generation replaces a manual process that previously required two days of staff work.',
        'authors': _authors(0, 1),
        'keywords': ['business intelligence', 'dashboard', 'financial reporting', 'analytics', 'web system'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 9, 'uploader_idx': 0, 'status': AP,
    },
    {
        'title': 'Social Media Sentiment Analysis Dashboard for Campus Events',
        'abstract': 'Scrapes Twitter/X and Facebook posts mentioning PampangaStateU campus events using the respective APIs, applies a fine-tuned RoBERTa sentiment classifier, and displays real-time sentiment gauges on a public-facing dashboard. Event organizers can monitor audience reception during live events and identify topics generating negative feedback for immediate response.',
        'authors': _authors(2, 3),
        'keywords': ['sentiment analysis', 'social media', 'NLP', 'RoBERTa', 'dashboard'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 2, 'status': AP,
    },
    {
        'title': 'Graduate Tracer Study Analytics System for Outcome Assessment',
        'abstract': 'Digitizes the annual graduate tracer survey and applies descriptive and inferential analytics to employment rates, job-program alignment, and postgraduate study rates by batch year and program. Longitudinal visualizations reveal how employment outcomes shift across economic conditions. Accreditation-ready reports are exportable in CHED-specified templates.',
        'authors': _authors(4, 5),
        'keywords': ['tracer study', 'analytics', 'graduate outcomes', 'CHED', 'web system'],
        'program': BSIS, 'year': 2022, 'adviser_idx': 0, 'uploader_idx': 4, 'status': AP,
    },
    {
        'title': 'Student Dropout Risk Analytics Using Historical Academic Records',
        'abstract': 'Builds a random forest classifier trained on five years of anonymized student records to predict dropout risk by end of first year. Features include first-semester GPA, scholarship status, commute distance, and remedial enrollment. The model achieves 84% AUC-ROC. High-risk students are surfaced in an adviser dashboard for proactive outreach, reducing dropout rates by an estimated 18% in a prospective pilot.',
        'authors': _authors(6, 7),
        'keywords': ['dropout prediction', 'analytics', 'random forest', 'student retention', 'machine learning'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 8, 'uploader_idx': 6, 'status': PR,
    },

    # ── CLUSTER 8: Cybersecurity and Access Control (9 theses) ───────────────
    {
        'title': 'Multi-Factor Authentication System for University Web Portals',
        'abstract': 'Adds TOTP-based two-factor authentication (RFC 6238) to the existing university portal login flow. Students and faculty enroll by scanning a QR code with any TOTP app; subsequent logins require a six-digit code after password entry. Emergency backup codes are generated during enrollment. Adoption reached 78% of active accounts within two months of opt-in rollout.',
        'authors': _authors(8, 9),
        'keywords': ['authentication', 'MFA', 'TOTP', 'security', 'web system'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 8, 'uploader_idx': 8, 'status': AP,
    },
    {
        'title': 'Role-Based Access Control Implementation for Academic Information Systems',
        'abstract': 'Designs and implements a fine-grained RBAC model for a university information system with seven defined roles (student, faculty, registrar, librarian, finance, IT admin, and executive). Permissions are stored in a policy table enabling runtime reconfiguration without code changes. An audit log captures all access-control decisions for compliance review.',
        'authors': _authors(10, 11),
        'keywords': ['access control', 'RBAC', 'authorization', 'security', 'information system'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 8, 'uploader_idx': 10, 'status': AP,
    },
    {
        'title': 'Intrusion Detection System for Campus Network Using Machine Learning',
        'abstract': 'Trains a gradient boosting classifier on the NSL-KDD dataset to classify network traffic as normal, DoS, probe, R2L, or U2R attack. The trained model is deployed as a real-time packet inspection service that integrates with the campus router via a mirrored port. During a two-week evaluation, the system detected 97.3% of injected attack traffic with a false positive rate of 1.8%.',
        'authors': _authors(12, 13),
        'keywords': ['intrusion detection', 'machine learning', 'network security', 'IDS', 'cybersecurity'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 8, 'uploader_idx': 12, 'status': AP,
    },
    {
        'title': 'End-to-End Encrypted File Sharing System for Academic Collaboration',
        'abstract': 'Implements client-side AES-256-GCM encryption before files are uploaded to cloud storage, ensuring that the server never has access to plaintext. Public-key exchange using X25519 enables secure key sharing between collaborators. A web interface allows faculty and students to create shared workspaces with granular read/write permissions.',
        'authors': _authors(14, 15),
        'keywords': ['encryption', 'file sharing', 'security', 'AES', 'collaboration'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 6, 'uploader_idx': 14, 'status': AP,
    },
    {
        'title': 'Blockchain-Based Academic Credential Verification System',
        'abstract': 'Issues tamper-evident digital diplomas and transcripts on a permissioned Hyperledger Fabric network. Graduates receive a QR code linking to the on-chain credential hash; verifiers scan the code to confirm authenticity without contacting the university registrar. The system eliminates paper-based verification delays and counterfeits. Piloted with 120 graduating CCS students.',
        'authors': _authors(16, 17),
        'keywords': ['blockchain', 'Hyperledger', 'credentials', 'verification', 'security'],
        'program': BSIT, 'year': 2025, 'adviser_idx': 0, 'uploader_idx': 16, 'status': AP,
    },
    {
        'title': 'Password Security Audit Tool for University IT Systems',
        'abstract': 'An internal tool that hashes existing password databases with multiple algorithms and checks hashes against a 10-million-entry weak-password corpus. Accounts with compromised or easily guessable passwords are flagged for forced reset. The audit discovered 12.4% of active accounts using passwords present in the HaveIBeenPwned dataset, prompting a university-wide password policy update.',
        'authors': _authors(18, 19),
        'keywords': ['password security', 'cybersecurity', 'audit', 'hashing', 'authentication'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 8, 'uploader_idx': 18, 'status': AP,
    },
    {
        'title': 'Web Application Vulnerability Scanner for Educational Websites',
        'abstract': 'Automates OWASP Top 10 vulnerability checks against web application endpoints including SQL injection detection, XSS reflection testing, CSRF token validation, and insecure direct object reference probing. Reports are generated in HTML and JSON format with remediation recommendations. Scanned 14 university department websites and reported 38 vulnerabilities, of which 31 were remediated within three weeks.',
        'authors': _authors(20, 21),
        'keywords': ['vulnerability scanner', 'OWASP', 'web security', 'penetration testing', 'cybersecurity'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 8, 'uploader_idx': 20, 'status': AP,
    },
    {
        'title': 'Secure Document Signing System Using Digital Certificates',
        'abstract': 'Issues X.509 certificates to faculty and staff for digitally signing official university documents such as memoranda and endorsement letters. The signing workflow integrates with the document management system so signatories apply their certificate-based signature within the browser. Recipients can verify signatures offline using any PDF reader that supports PKCS#7 signature validation.',
        'authors': _authors(22, 23),
        'keywords': ['digital signature', 'X.509', 'security', 'PKI', 'document management'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 8, 'uploader_idx': 22, 'status': AP,
    },
    {
        'title': 'Privacy-Preserving Data Anonymization Tool for Student Research Datasets',
        'abstract': 'Implements k-anonymity and l-diversity algorithms to anonymize student demographic datasets before sharing with external researchers. A Tkinter-based desktop GUI allows researchers to select quasi-identifier columns and set privacy parameter k. The tool validates that the output dataset satisfies the selected privacy model and generates a provenance report documenting applied transformations.',
        'authors': _authors(24, 25),
        'keywords': ['data privacy', 'anonymization', 'k-anonymity', 'cybersecurity', 'research'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 6, 'uploader_idx': 24, 'status': RJ,
    },

    # ── CLUSTER 9: Mobile Applications (9 theses) ────────────────────────────
    {
        'title': 'Campus Navigation Mobile App with Augmented Reality Overlays',
        'abstract': 'A React Native app that overlays directional arrows and building labels on the smartphone camera feed using ARCore and ARKit to guide visitors around the PampangaStateU campus. Points of interest include offices, laboratories, canteens, and comfort rooms. User tests with 40 first-year students showed an 87% task-completion rate for navigating to an unfamiliar building on first attempt.',
        'authors': _authors(26, 27),
        'keywords': ['mobile', 'augmented reality', 'navigation', 'ARCore', 'campus'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 7, 'uploader_idx': 26, 'status': AP,
    },
    {
        'title': 'Scholarship Application and Tracking Mobile Application',
        'abstract': 'A Flutter app through which students apply for internal and external scholarships, upload documentary requirements, and track application status in real time. Scholarship coordinators receive push notifications for new applications and can approve or request additional documents from within the app. 95% of applicants rated the mobile process as easier than the previous paper-based system.',
        'authors': _authors(28, 29),
        'keywords': ['mobile', 'scholarship', 'Flutter', 'document management', 'student services'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 5, 'uploader_idx': 28, 'status': AP,
    },
    {
        'title': 'Event Management and Registration Mobile App for University Organizations',
        'abstract': 'A React Native application that allows student organizations to publish events, manage registration slots, collect participation fees via GCash integration, and issue QR-code digital tickets. Attendance is recorded by scanning tickets at the venue entrance. Post-event analytics show attendance demographics and feedback ratings for organization officers.',
        'authors': _authors(30, 31),
        'keywords': ['mobile', 'event management', 'React Native', 'QR code', 'student organizations'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 5, 'uploader_idx': 30, 'status': AP,
    },
    {
        'title': 'Language Learning Mobile App for Filipino Students Studying Japanese',
        'abstract': 'A gamified Flutter app teaching hiragana, katakana, and basic Kanji through spaced repetition flashcards, mini-games, and daily streak rewards. Filipino cultural references are used in example sentences to improve relatability. In a 30-day study with 50 BSIT students, users retained 73% of vocabulary items compared to 48% in the control group using a textbook-only approach.',
        'authors': _authors(32, 33),
        'keywords': ['mobile', 'language learning', 'Flutter', 'gamification', 'Japanese'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 7, 'uploader_idx': 32, 'status': AP,
    },
    {
        'title': 'Parking Reservation and Payment Mobile App for Campus Commuters',
        'abstract': 'Allows registered vehicle owners to reserve a specific parking bay in advance and pay the daily fee through GCash or credit card. Reserved bays are held for 15 minutes after the booking start time before being released back to walk-in drivers. Integration with the IoT parking sensor system updates bay availability in real time.',
        'authors': _authors(34, 0),
        'keywords': ['mobile', 'parking', 'reservation', 'payment', 'campus'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 3, 'uploader_idx': 34, 'status': AP,
    },
    {
        'title': 'Disaster Preparedness and Evacuation Guide Mobile App',
        'abstract': 'Provides offline-accessible evacuation route maps, shelter locations, and emergency contact lists for Pampanga residents. During a declared emergency, the app displays color-coded flood-risk zones sourced from PAGASA data and broadcasts push notifications from LGU civil defense officers. Designed for low-bandwidth conditions with a maximum app size of 8 MB.',
        'authors': _authors(1, 2),
        'keywords': ['mobile', 'disaster preparedness', 'evacuation', 'offline', 'emergency'],
        'program': BSIT, 'year': 2022, 'adviser_idx': 7, 'uploader_idx': 1, 'status': AP,
    },
    {
        'title': 'Budgeting and Expense Tracking App for Filipino College Students',
        'abstract': 'A lightweight React Native budgeting app designed around the financial realities of Philippine college students, supporting weekly rather than monthly budgets and common local expense categories (transpo, load, pagkain). Expense entry takes under three taps. After eight weeks of use, 68% of pilot participants reported spending within their weekly budget more consistently.',
        'authors': _authors(3, 4),
        'keywords': ['mobile', 'budgeting', 'finance', 'React Native', 'student life'],
        'program': BSIT, 'year': 2023, 'adviser_idx': 9, 'uploader_idx': 3, 'status': AP,
    },
    {
        'title': 'Job Matching Mobile App for Fresh Graduates Using Skills Tagging',
        'abstract': 'Graduates tag their skills and preferred industries during profile setup; the app matches them with employers who post job openings with required skill tags. A compatibility score ranks openings by tag overlap. In-app messaging allows direct employer-applicant communication. Three months after launch, 47 graduates from PampangaStateU secured interviews through the platform.',
        'authors': _authors(5, 6),
        'keywords': ['mobile', 'job matching', 'graduates', 'skills tagging', 'employment'],
        'program': BSIT, 'year': 2025, 'adviser_idx': 5, 'uploader_idx': 5, 'status': AP,
    },
    {
        'title': 'Sign Language Translation Mobile App Using Hand Gesture Recognition',
        'abstract': 'Uses MediaPipe Hands to extract 21 hand landmark points per frame from the smartphone camera feed and feeds them into a trained LSTM model to recognize 40 Filipino Sign Language gestures. Recognition results are displayed as text and spoken via text-to-speech. Two-way communication is supported: a speech-to-gesture animation feature helps hearing users communicate with Deaf users.',
        'authors': _authors(7, 8),
        'keywords': ['mobile', 'sign language', 'MediaPipe', 'LSTM', 'accessibility'],
        'program': BSIT, 'year': 2024, 'adviser_idx': 7, 'uploader_idx': 7, 'status': RJ,
    },

    # ── CLUSTER 10: Thesis Repository / Research Management (8 theses) ───────
    # Semantic sub-cluster: thesis repository systems (different wording, same domain)
    {
        'title': 'THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System',
        'abstract': 'Presents THESYS+, a web-based thesis repository for PampangaStateU CCS that combines SBERT semantic search with cosine similarity ranking to surface contextually relevant theses beyond simple keyword matching. A topic trend analysis module clusters thesis abstracts with k-means to reveal research focus shifts across academic years. An admin-governed upload and approval workflow ensures repository quality.',
        'authors': _authors(9, 10),
        'keywords': ['thesis repository', 'semantic search', 'SBERT', 'trend analysis', 'research management'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 1, 'uploader_idx': 9, 'status': AP,
    },
    {
        'title': 'Digital Thesis Repository with Full-Text Search and Metadata Filtering',
        'abstract': 'A Django-powered institutional repository for CCS capstone theses with PDF text extraction via PyMuPDF, full-text search using PostgreSQL tsvector, and faceted filtering by program, year, and adviser. Students can browse theses, download approved documents, and view abstract previews without authentication. An admin portal manages the upload approval workflow.',
        'authors': _authors(11, 12),
        'keywords': ['thesis repository', 'full-text search', 'metadata', 'Django', 'digital library'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 11, 'status': AP,
    },
    {
        'title': 'Intelligent Research Paper Discovery Platform Using Embedding-Based Search',
        'abstract': 'Embeds academic paper abstracts using Sentence-BERT and stores 384-dimensional vectors in a FAISS index for sub-millisecond approximate nearest-neighbor retrieval. A query expansion module reformulates short user queries into richer sentence representations. Evaluated on a corpus of 1,500 Philippine university theses, the system achieves MRR@10 of 0.78 against human-labeled relevance judgments.',
        'authors': _authors(13, 14),
        'keywords': ['semantic search', 'SBERT', 'FAISS', 'research discovery', 'embeddings'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 6, 'uploader_idx': 13, 'status': AP,
    },
    {
        'title': 'Research Collaboration Matchmaking System for University Faculty',
        'abstract': 'Analyzes faculty research profiles and publication abstracts using TF-IDF and SBERT embeddings to compute pairwise research similarity scores. Potential collaborators with overlapping but non-identical research interests are surfaced to encourage cross-disciplinary projects. Faculty can indicate interest in collaboration, triggering a mutual-interest notification to both parties.',
        'authors': _authors(15, 16),
        'keywords': ['research collaboration', 'SBERT', 'TF-IDF', 'faculty', 'matching'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 15, 'status': AP,
    },
    {
        'title': 'Automated Thesis Title Similarity Checker for Originality Verification',
        'abstract': 'Computes cosine similarity between a candidate thesis title embedding and all stored thesis title embeddings to flag potentially duplicative work before a student proceeds with their proposal. Results are presented as a ranked list of existing theses with similarity scores. Panel chairs reported a 44% reduction in proposal rejection due to duplicated topics after the system was deployed.',
        'authors': _authors(17, 18),
        'keywords': ['title similarity', 'cosine similarity', 'originality', 'thesis', 'research management'],
        'program': BSCS, 'year': 2025, 'adviser_idx': 6, 'uploader_idx': 17, 'status': AP,
    },
    {
        'title': 'Research Topic Trend Visualization for Computing Departments',
        'abstract': 'Applies LDA topic modeling and k-means clustering to five years of CCS thesis abstracts to identify evolving research themes. An interactive D3.js dashboard displays topic prevalence per year and provides drill-down to individual thesis records per cluster. Department chairs used the visualizations to justify curriculum updates aligning with emerging industry trends.',
        'authors': _authors(19, 20),
        'keywords': ['topic modeling', 'LDA', 'trend analysis', 'research', 'visualization'],
        'program': BSCS, 'year': 2024, 'adviser_idx': 1, 'uploader_idx': 19, 'status': AP,
    },
    {
        'title': 'Plagiarism Detection System for Student Research Papers',
        'abstract': 'Implements fingerprint-based document similarity detection using shingling and MinHash LSH to identify near-duplicate passages across a corpus of submitted student research papers. Integration with the submission portal flags potential plagiarism before the document reaches the adviser. A detailed match report highlights specific overlapping passages and links to the source document.',
        'authors': _authors(21, 22),
        'keywords': ['plagiarism detection', 'MinHash', 'LSH', 'research integrity', 'document similarity'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 8, 'uploader_idx': 21, 'status': AP,
    },
    {
        'title': 'Citation Network Analysis Tool for Identifying Research Gaps',
        'abstract': 'Constructs a citation graph from reference lists extracted by the Grobid parser applied to thesis PDFs. Network centrality metrics (betweenness, PageRank) identify seminal works in the local corpus. Disconnected subgraphs in the citation network indicate under-cited research areas interpreted as potential gaps for future thesis topics. Visualized using Sigma.js.',
        'authors': _authors(23, 24),
        'keywords': ['citation analysis', 'network graph', 'research gaps', 'NLP', 'thesis repository'],
        'program': BSCS, 'year': 2023, 'adviser_idx': 6, 'uploader_idx': 23, 'status': RJ,
    },
]


# ── PDF builder (reused from seed_theses.py) ─────────────────────────────

def _build_minimal_pdf(title: str, abstract: str) -> bytes:
    """Create a tiny, valid one-page PDF carrying the title + abstract."""
    safe_title    = title.replace('(', '\\(').replace(')', '\\)')
    safe_abstract = abstract.replace('(', '\\(').replace(')', '\\)')
    body_text = f'TITLE: {safe_title}\\nABSTRACT: {safe_abstract}'
    content = f'BT /F1 12 Tf 50 750 Td ({body_text}) Tj ET'.encode('latin-1', errors='replace')
    parts = [b'%PDF-1.4\n']
    obj1_offset = len(b''.join(parts))
    parts.append(b'1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n')
    obj2_offset = len(b''.join(parts))
    parts.append(b'2 0 obj <</Type /Pages /Count 1 /Kids [3 0 R]>> endobj\n')
    obj3_offset = len(b''.join(parts))
    parts.append(
        b'3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Contents 4 0 R /Resources <</Font <</F1 <</Type /Font '
        b'/Subtype /Type1 /BaseFont /Helvetica>>>>>>>> endobj\n'
    )
    obj4_offset = len(b''.join(parts))
    stream_obj = (
        f'4 0 obj <</Length {len(content)}>>\nstream\n'.encode('latin-1')
        + content + b'\nendstream endobj\n'
    )
    parts.append(stream_obj)
    xref_offset = len(b''.join(parts))
    xref = (
        b'xref\n0 5\n0000000000 65535 f \n'
        + f'{obj1_offset:010d} 00000 n \n'.encode('latin-1')
        + f'{obj2_offset:010d} 00000 n \n'.encode('latin-1')
        + f'{obj3_offset:010d} 00000 n \n'.encode('latin-1')
        + f'{obj4_offset:010d} 00000 n \n'.encode('latin-1')
    )
    parts.append(xref)
    parts.append(
        b'trailer <</Size 5 /Root 1 0 R>>\nstartxref\n'
        + f'{xref_offset}\n'.encode('latin-1')
        + b'%%EOF\n'
    )
    return b''.join(parts)


# ── Management command ────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Seed THESYS+ with 50 demo users and 100 realistic theses '
        'for prototype defense demonstration.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-embeddings',
            action='store_true',
            help='Create thesis records without generating SBERT embeddings (fast mode).',
        )
        parser.add_argument(
            '--regenerate-embeddings',
            action='store_true',
            help='Re-embed all demo theses regardless of current embedding status.',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all demo users and their theses before re-seeding.',
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        skip_emb  = options['skip_embeddings']
        regen_emb = options['regenerate_embeddings']
        do_reset  = options['reset']

        # ── Optional reset ────────────────────────────────────────────
        if do_reset:
            thesis_count = Thesis.objects.filter(
                uploaded_by__email__in=list(ALL_DEMO_EMAILS)
            ).count()
            Thesis.objects.filter(
                uploaded_by__email__in=list(ALL_DEMO_EMAILS)
            ).delete()
            user_count = User.objects.filter(email__in=list(ALL_DEMO_EMAILS)).count()
            User.objects.filter(email__in=list(ALL_DEMO_EMAILS)).delete()
            self.stdout.write(self.style.WARNING(
                f'Reset: deleted {thesis_count} theses and {user_count} demo users.'
            ))

        # ── Step 1: Create users ──────────────────────────────────────
        self.stdout.write('Creating users...')
        users_created, users_skipped = self._seed_users()
        self.stdout.write(self.style.SUCCESS(
            f'  Users: {users_created} created, {users_skipped} already existed.'
        ))

        # Build email→User lookup for thesis provenance
        all_emails = STUDENT_EMAILS + FACULTY_EMAILS + ADMIN_EMAILS
        user_map = {u.email: u for u in User.objects.filter(email__in=all_emails)}

        # ── Step 2: Create theses ─────────────────────────────────────
        self.stdout.write('Creating theses...')
        theses_created, theses_skipped, created_thesis_objects = self._seed_theses(user_map)
        self.stdout.write(self.style.SUCCESS(
            f'  Theses: {theses_created} created, {theses_skipped} already existed.'
        ))

        # ── Step 3: Generate embeddings ───────────────────────────────
        if skip_emb:
            self.stdout.write(self.style.NOTICE(
                'Skipping embedding generation (--skip-embeddings). '
                'Run: python manage.py embed_theses'
            ))
        else:
            self._generate_embeddings(created_thesis_objects, regen=regen_emb)

        # ── Summary ───────────────────────────────────────────────────
        self._print_summary()

    # ------------------------------------------------------------------
    def _seed_users(self):
        created = 0
        skipped = 0

        # Students
        for i, email in enumerate(STUDENT_EMAILS):
            n = STUDENT_NAMES[i % len(STUDENT_NAMES)]
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': n[1],
                    'last_name': n[0],
                    'role': Role.STUDENT,
                    'is_active': True,
                    'is_email_verified': True,
                },
            )
            if was_created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=['password'])
                created += 1
            else:
                skipped += 1

        # Faculty
        for fac in FACULTY_USERS:
            user, was_created = User.objects.get_or_create(
                email=fac['email'],
                defaults={
                    'first_name': fac['first'],
                    'last_name': fac['last'],
                    'role': Role.FACULTY,
                    'is_active': True,
                    'is_email_verified': True,
                },
            )
            if was_created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=['password'])
                created += 1
            else:
                skipped += 1

        # Admins
        for i, email in enumerate(ADMIN_EMAILS):
            n = ADMIN_NAMES[i]
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': n[1],
                    'last_name': n[0],
                    'role': Role.ADMINISTRATOR,
                    'is_active': True,
                    'is_email_verified': True,
                },
            )
            if was_created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=['password'])
                created += 1
            else:
                skipped += 1

        return created, skipped

    # ------------------------------------------------------------------
    def _seed_theses(self, user_map):
        import hashlib as _hashlib
        created = 0
        skipped = 0
        created_objects = []

        # Faculty users as fallback uploaders for any thesis
        faculty_users = [user_map[e] for e in FACULTY_EMAILS if e in user_map]

        for entry in THESES_DATA:
            if Thesis.objects.filter(title=entry['title']).exists():
                skipped += 1
                continue

            # Resolve uploader: student by index (uploaded on behalf of faculty adviser)
            stu_email = STUDENT_EMAILS[entry['uploader_idx'] % len(STUDENT_EMAILS)]
            uploader  = user_map.get(stu_email) or faculty_users[0]

            # Resolve reviewer: the faculty adviser
            fac_email = FACULTY_EMAILS[entry['adviser_idx'] % len(FACULTY_EMAILS)]
            reviewer  = user_map.get(fac_email) or faculty_users[0]

            adviser_str = _adviser(entry['adviser_idx'])
            status      = entry['status']

            pdf_bytes = _build_minimal_pdf(entry['title'], entry['abstract'])
            sha256    = _hashlib.sha256(pdf_bytes).hexdigest()

            reviewed_at = timezone.now() if status in (
                ThesisStatus.APPROVED.value, ThesisStatus.REJECTED.value
            ) else None

            rejection_reason = ''
            if status == ThesisStatus.REJECTED.value:
                rejection_reason = (
                    'Thesis proposal does not meet the minimum originality requirements. '
                    'Please revise the research scope and resubmit.'
                )

            with transaction.atomic():
                thesis = Thesis(
                    title=entry['title'],
                    abstract=entry['abstract'],
                    authors=entry['authors'],
                    keywords=entry['keywords'],
                    program=entry['program'],
                    year=entry['year'],
                    adviser=adviser_str,
                    file_type=FileType.PDF,
                    sha256=sha256,
                    extracted_text=f"{entry['title']}\n\n{entry['abstract']}",
                    embedding_status=EmbeddingStatus.NOT_STARTED,
                    status=status,
                    uploaded_by=uploader,
                    reviewed_by=reviewer if reviewed_at else None,
                    reviewed_at=reviewed_at,
                    rejection_reason=rejection_reason,
                )
                safe_name = ''.join(
                    c if c.isalnum() else '_' for c in entry['title']
                )[:60]
                thesis.uploaded_file.save(
                    f'{safe_name}.pdf',
                    ContentFile(pdf_bytes),
                    save=False,
                )
                thesis.save()

            created += 1
            # Only generate embeddings for approved theses (matches production behavior)
            if status == ThesisStatus.APPROVED.value:
                created_objects.append(thesis)

        return created, skipped, created_objects

    # ------------------------------------------------------------------
    def _generate_embeddings(self, thesis_objects, *, regen: bool = False):
        from theses.services.semantic_search import generate_thesis_embedding, MODEL_NAME

        if regen:
            # Re-embed all approved demo theses
            demo_emails = list(ALL_DEMO_EMAILS)
            qs = list(
                Thesis.objects.filter(
                    uploaded_by__email__in=demo_emails,
                    status=ThesisStatus.APPROVED.value,
                ).order_by('created_at')
            )
            self.stdout.write(self.style.WARNING(
                f'Regenerating embeddings for {len(qs)} approved demo theses '
                f'using {MODEL_NAME}…'
            ))
        else:
            qs = thesis_objects
            self.stdout.write(self.style.NOTICE(
                f'Generating embeddings for {len(qs)} newly created approved theses '
                f'using {MODEL_NAME}…'
            ))

        if not qs:
            self.stdout.write('  No theses require embedding.')
            return

        ok = 0
        failed = 0
        for thesis in qs:
            try:
                generate_thesis_embedding(thesis)
                ok += 1
                self.stdout.write(f'  [OK] {thesis.title[:70]}')
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  [FAIL] {thesis.title[:70]} -- {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'  Embeddings: {ok} generated, {failed} failed.'
        ))

    # ------------------------------------------------------------------
    def _print_summary(self):
        from django.db.models import Count

        demo_emails = list(ALL_DEMO_EMAILS)
        total_theses = Thesis.objects.filter(
            uploaded_by__email__in=demo_emails
        ).count()

        self.stdout.write('\n' + '-' * 60)
        self.stdout.write(self.style.SUCCESS('SEED SUMMARY'))
        self.stdout.write('-' * 60)

        # User counts
        students = User.objects.filter(email__in=STUDENT_EMAILS).count()
        faculty  = User.objects.filter(email__in=FACULTY_EMAILS).count()
        admins   = User.objects.filter(email__in=ADMIN_EMAILS).count()
        self.stdout.write(f'Users total   : {students + faculty + admins}')
        self.stdout.write(f'  Students    : {students}')
        self.stdout.write(f'  Faculty     : {faculty}')
        self.stdout.write(f'  Admins      : {admins}')

        self.stdout.write(f'\nTheses total  : {total_theses}')

        # Status breakdown
        for status_val, label in ThesisStatus.choices:
            n = Thesis.objects.filter(
                uploaded_by__email__in=demo_emails,
                status=status_val,
            ).count()
            self.stdout.write(f'  {label:<20}: {n}')

        # Program breakdown
        self.stdout.write('')
        for prog_val, prog_label in [
            (Program.BSIS.value, 'BSIS'),
            (Program.BSIT.value, 'BSIT'),
            (Program.BSCS.value, 'BSCS'),
            (Program.ACT.value,  'ACT'),
        ]:
            n = Thesis.objects.filter(
                uploaded_by__email__in=demo_emails,
                program=prog_val,
            ).count()
            if n:
                self.stdout.write(f'  {prog_label:<20}: {n}')

        # Year breakdown
        self.stdout.write('')
        year_data = (
            Thesis.objects.filter(uploaded_by__email__in=demo_emails)
            .values('year')
            .annotate(n=Count('id'))
            .order_by('year')
        )
        for row in year_data:
            self.stdout.write(f'  {row["year"]}                : {row["n"]}')

        # Embedding status
        embedded = Thesis.objects.filter(
            uploaded_by__email__in=demo_emails,
            embedding_status=EmbeddingStatus.READY.value,
        ).count()
        self.stdout.write(f'\nEmbedded (ready): {embedded} / {total_theses}')
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.SUCCESS('Seed complete.'))
