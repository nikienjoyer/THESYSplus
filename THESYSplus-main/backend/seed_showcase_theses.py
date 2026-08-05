"""Showcase seeding script — 105 theses spanning 2023-2025.

Purpose: populate the repository with realistic-looking thesis records so
the Title Similarity, Analytics, and Trend Analysis pages have enough data
to demo meaningfully. All records are status=APPROVED (Analytics/Trend
Analysis/Title Similarity all read from the approved subset) and each gets
an SBERT embedding generated immediately so Title Similarity / semantic
search can rank them against each other.

Dataset design:
    105 theses, years restricted to 2023 / 2024 / 2025 only.
    Program split: 40 BS Computer Science, 35 BS Information Technology,
    30 BS Information System.

    Tech-trend shift (BSCS in particular):
      2023 — classical ML / web / mobile, pre-GenAI
      2024 — Generative AI, LLMs, Computer Vision spike begins
      2025 — GenAI/LLM/CV intensifies (multimodal, agentic, fine-tuned)

    BSIT/BSIS keep their usual web/mobile/IoT/BI focus with only a light,
    secondary AI uptake in 2024-2025 — so the BSCS spike reads clearly
    against a comparatively stable baseline.

    6 explicit near-duplicate title pairs (12 records) are seeded across
    the corpus to exercise the Title Similarity page, including the
    crop-yield-prediction example from the task brief.

Usage:
    python manage.py shell < seed_showcase_theses.py
    python seed_showcase_theses.py

Idempotent: records are skipped by exact title match, so re-running the
script does not create duplicates.
"""

from __future__ import annotations

import hashlib
import itertools
import random
import re


def _bootstrap_django() -> None:
    """Set up Django when run as a standalone script (no-op under manage.py shell)."""
    from django.apps import apps
    if apps.ready:
        return
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
    import django
    django.setup()


_bootstrap_django()

from django.core.files.base import ContentFile  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import Role, User  # noqa: E402
from theses.models import FileType, Program, Thesis, ThesisStatus  # noqa: E402
from theses.services.semantic_search import generate_thesis_embedding  # noqa: E402


SEED_USER_EMAIL = 'showcase-seed-bot@pampangastateu.edu.ph'

BSCS = Program.BSCS.value
BSIT = Program.BSIT.value
BSIS = Program.BSIS.value

STOP_WORDS = {
    'based', 'system', 'systems', 'for', 'and', 'a', 'an', 'of', 'the',
    'using', 'to', 'at', 'style', 'style-', 'ai-', 'llm',
}

TITLE_TEMPLATES = [
    '{technique} System for {domain}',
    '{technique} Approach to {domain}',
    '{technique} Platform for {domain}',
    'A {technique} Framework for {domain}',
    '{technique} Solution for {domain} at Pampanga State University',
]

STUDENT_NAME_POOL = [
    ('Dela Cruz', 'Miguel'), ('Santos', 'Ana'), ('Reyes', 'Carlo'), ('Garcia', 'Bianca'),
    ('Lopez', 'Diego'), ('Torres', 'Isabel'), ('Cruz', 'Rafael'), ('Tan', 'Camille'),
    ('Aquino', 'Nathan'), ('Ramos', 'Sophia'), ('Bautista', 'Julian'), ('Mercado', 'Alexa'),
    ('Yap', 'Gabriel'), ('Navarro', 'Erika'), ('Castillo', 'Miko'), ('Dizon', 'Trisha'),
]

FACULTY_NAME_POOL = [
    'Prof. Reyes, Roberto', 'Dr. Villanueva, Carmen', 'Engr. Mendoza, Luis',
    'Prof. Tan, Miguel', 'Dr. Ramos, Patricia', 'Dr. Sy, Christopher',
]


# ---------------------------------------------------------------------------
# Word banks — technique / domain pools per (program, year)
# ---------------------------------------------------------------------------

POOLS = {
    (BSCS, 2023): dict(
        techniques=['Decision Tree', 'Random Forest', 'Support Vector Machine',
                    'K-Nearest Neighbors', 'Naive Bayes', 'Rule-Based Expert',
                    'Cross-Platform Mobile'],
        domains=['Student Dropout Risk Prediction', 'Traffic Flow Forecasting',
                 'Loan Default Risk Assessment', 'Weather Pattern Forecasting',
                 'Exam Performance Prediction', 'Restaurant Recommendation',
                 'Personal Fitness Tracking', 'Campus Navigation Assistance'],
    ),
    (BSCS, 2024): dict(
        techniques=['GPT-Based', 'Retrieval-Augmented Generation (RAG)',
                    'Generative Adversarial Network (GAN)', 'Vision Transformer',
                    'YOLOv8-Based', 'Prompt-Engineered LLM', 'Fine-Tuned Transformer'],
        domains=['Thesis Writing Assistance', 'Customer Support Chatbot',
                 'Code Review Assistance', 'Medical Image Segmentation',
                 'Document Summarization', 'Plagiarism and Paraphrase Detection',
                 'Synthetic Agricultural Data Augmentation', 'Resume Screening Automation'],
    ),
    (BSCS, 2025): dict(
        techniques=['Multimodal Large Language Model', 'Agentic AI',
                    'Diffusion-Based Generative', 'Vision-Language Model',
                    'Chain-of-Thought Prompted LLM', 'Open-Source LLM (Llama)-Powered',
                    'Multi-Agent LLM'],
        domains=['Academic Advising Assistance', 'Automated Thesis Structure Checking',
                 'AI-Generated Art Detection', 'Personalized Learning Content Generation',
                 'Video Lecture Summarization', 'Autonomous Literature Review',
                 'AI-Assisted Software Testing', 'Multimodal Sentiment Analysis'],
    ),
    (BSIT, 2023): dict(
        techniques=['Web-Based', 'Android-Based', 'IoT-Based', 'Cloud-Hosted',
                    'Cross-Platform Mobile'],
        domains=['Hotel Reservation Management', 'Barangay Records Management',
                 'Clinic Appointment Scheduling', 'Parking Slot Reservation',
                 'Fleet Vehicle Tracking', 'Church Donation and Membership Management',
                 'Gym Membership Management', 'Event Ticketing',
                 'Courier Delivery Tracking', 'Sari-Sari Store Point-of-Sale'],
    ),
    (BSIT, 2024): dict(
        techniques=['Cloud-Native', 'Progressive Web App (PWA)', 'Microservices-Based',
                    'IoT and Edge Computing', 'Chatbot-Integrated Web'],
        domains=['Customer Support Ticketing', 'Smart Irrigation Control',
                 'Property Rental Marketplace', 'Freelancer Job Matching',
                 'Telemedicine Consultation Booking', 'Food Delivery Logistics',
                 'Warehouse Robotics Coordination', 'Digital Wallet and Micro-Payments',
                 'Hotel Booking Recommendation'],
    ),
    (BSIT, 2025): dict(
        techniques=['AI-Enhanced Cloud', 'Edge AI', 'Serverless', 'Voice-Assisted IoT',
                    'Blockchain-Secured'],
        domains=['Smart Traffic Signal Control', 'Digital Twin Facility Monitoring',
                 'Predictive Fleet Maintenance', 'Contactless Campus Access Control',
                 'Personalized E-Commerce Recommendation', 'Smart Energy Consumption Monitoring',
                 'Automated Helpdesk Support', 'Real-Time Delivery Route Optimization',
                 'Smart Building Access Management', 'Voice-Controlled Home Automation'],
    ),
    (BSIS, 2023): dict(
        techniques=['Web-Based', 'Decision Support', 'Enterprise Resource Planning (ERP)-Style',
                    'Management Information'],
        domains=['Hospital Patient Records Management', 'Cooperative Loan and Savings Management',
                 'School Enrollment and Registration', 'Church Financial Management',
                 'Barangay Health Records Management', 'Real Estate Listing Management',
                 'Warehouse Order Fulfillment', 'Municipal Business Permit Processing',
                 'Cemetery Lot Records Management'],
    ),
    (BSIS, 2024): dict(
        techniques=['Business Intelligence (BI)', 'Robotic Process Automation (RPA)-Enabled',
                    'Cloud ERP', 'Data Warehouse-Backed'],
        domains=['Sales Performance Dashboard', 'Municipal Tax Collection',
                 'Supply Chain Visibility', 'University Alumni Relationship Management',
                 'Employee Performance Evaluation', 'Procurement and Vendor Management',
                 'Hospital Billing and Claims Processing', 'Cooperative Member Records Management',
                 'School Fee Collection'],
    ),
    (BSIS, 2025): dict(
        techniques=['AI-Augmented Business Intelligence', 'Predictive Analytics-Driven',
                    'Chatbot-Assisted Decision Support', 'Automated RPA'],
        domains=['Financial Fraud Detection', 'Customer Churn Prediction',
                 'Inventory Demand Forecasting', 'Human Resource Attrition Analysis',
                 'Loan Approval Risk Scoring', 'Retail Sales Forecasting',
                 'Employee Attendance Analytics', 'Municipal Revenue Forecasting',
                 'Vendor Performance Scoring', 'Enrollment Demand Forecasting'],
    ),
}

# How many templated (non-paired) records to generate per (program, year) bucket.
BUCKET_COUNTS = {
    (BSCS, 2023): 8, (BSCS, 2024): 13, (BSCS, 2025): 13,
    (BSIT, 2023): 11, (BSIT, 2024): 10, (BSIT, 2025): 10,
    (BSIS, 2023): 9, (BSIS, 2024): 9, (BSIS, 2025): 10,
}


# ---------------------------------------------------------------------------
# Hand-authored near-duplicate pairs — exercises the Title Similarity page.
# ---------------------------------------------------------------------------

SIMILAR_PAIRS = [
    # The task brief's own example.
    ('Predictive Crop Yield Analysis Using Machine Learning Algorithms', BSCS, 2023,
     ['machine learning', 'crop yield', 'agriculture', 'prediction']),
    ('Machine Learning Approaches for Agricultural Yield Prediction in Local Farms', BSCS, 2023,
     ['machine learning', 'agricultural yield', 'prediction', 'farming']),

    ('GPT-Based Chatbot for Automated Student Academic Advising', BSCS, 2024,
     ['GPT', 'chatbot', 'academic advising', 'LLM']),
    ('Large Language Model-Powered Virtual Assistant for Academic Advising Support', BSCS, 2025,
     ['large language model', 'virtual assistant', 'academic advising']),

    ('Deep Learning-Based Detection of AI-Generated Deepfake Images', BSCS, 2024,
     ['deep learning', 'deepfake', 'detection', 'computer vision']),
    ('Convolutional Neural Network Approach for Identifying AI-Generated Facial Deepfakes', BSCS, 2025,
     ['CNN', 'deepfake', 'facial recognition', 'computer vision']),

    ('IoT-Based Water Refilling Station Monitoring and Automation System', BSIT, 2023,
     ['IoT', 'water refilling station', 'monitoring', 'automation']),
    ('Automated Monitoring System for Water Refilling Stations Using IoT Sensors', BSIT, 2024,
     ['IoT sensors', 'water refilling station', 'monitoring', 'automation']),

    ('Web-Based Payroll and Human Resource Management System for Small Enterprises', BSIS, 2023,
     ['payroll', 'human resource', 'management system', 'web system']),
    ('Human Resource and Payroll Information System for Small and Medium Enterprises', BSIS, 2024,
     ['human resource', 'payroll', 'information system']),

    ('Chatbot-Integrated Web System for Customer Support Ticket Management', BSIT, 2024,
     ['chatbot', 'customer support', 'ticketing', 'web system']),
    ('AI Chat-Assisted Helpdesk Platform for Customer Support Automation', BSIT, 2025,
     ['AI chatbot', 'helpdesk', 'customer support', 'automation']),
]


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def _keywords_from(*phrases: str) -> list[str]:
    words: list[str] = []
    for phrase in phrases:
        for token in re.split(r'[^A-Za-z0-9]+', phrase):
            t = token.lower()
            if t and t not in STOP_WORDS and t not in words:
                words.append(t)
    return words[:6]


def _abstract_for(technique: str, domain: str, program_label: str, idx: int) -> str:
    metric = 85 + (idx % 12)
    return (
        f'This study presents a {technique.lower()} solution addressing {domain.lower()} '
        f'for the {program_label} research track at Pampanga State University College of '
        f'Computing Studies. The prototype was implemented and evaluated against a locally '
        f'gathered dataset, achieving an evaluation score of approximately {metric}% on the '
        f'primary performance metric. Results suggest the approach is a practical, deployable '
        f'proof of concept for real-world {domain.lower()} scenarios in the Philippine higher '
        f'education and industry context.'
    )


def _bucket_records(program: str, year: int, count: int, start_idx: int) -> list[dict]:
    pool = POOLS[(program, year)]
    combos = list(itertools.product(pool['techniques'], pool['domains']))
    rng = random.Random(hash((program, year)) & 0xFFFFFFFF)
    rng.shuffle(combos)
    selected = combos[:count]

    records = []
    for i, (technique, domain) in enumerate(selected):
        idx = start_idx + i
        template = TITLE_TEMPLATES[idx % len(TITLE_TEMPLATES)]
        title = template.format(technique=technique, domain=domain)
        records.append({
            'title': title,
            'abstract': _abstract_for(technique, domain, program, idx),
            'keywords': _keywords_from(technique, domain),
            'program': program,
            'year': year,
        })
    return records


def _build_all_records() -> list[dict]:
    records: list[dict] = []
    idx = 0
    for title, program, year, keywords in SIMILAR_PAIRS:
        records.append({
            'title': title,
            'abstract': (
                f'This study explores {title[:1].lower()}{title[1:].rstrip(".")} as applied '
                f'at Pampanga State University College of Computing Studies, presenting an '
                f'implementation evaluated on a locally gathered dataset with results comparable '
                f'to similar academic literature in the field.'
            ),
            'keywords': keywords,
            'program': program,
            'year': year,
        })
        idx += 1

    for (program, year), count in BUCKET_COUNTS.items():
        records.extend(_bucket_records(program, year, count, idx))
        idx += count

    return records


def _authors_for(idx: int) -> list[str]:
    a = STUDENT_NAME_POOL[idx % len(STUDENT_NAME_POOL)]
    b = STUDENT_NAME_POOL[(idx + 1) % len(STUDENT_NAME_POOL)]
    return [f'{a[0]}, {a[1]}', f'{b[0]}, {b[1]}']


def _adviser_for(idx: int) -> str:
    return FACULTY_NAME_POOL[idx % len(FACULTY_NAME_POOL)]


def _get_seed_user() -> User:
    user, created = User.objects.get_or_create(
        email=SEED_USER_EMAIL,
        defaults={
            'first_name': 'THESYS+',
            'last_name': 'Showcase Bot',
            'role': Role.FACULTY,
            'is_active': True,
            'is_email_verified': True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save()
    return user


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    user = _get_seed_user()
    records = _build_all_records()
    assert len(records) == 105, f'Expected 105 records, built {len(records)}'

    created_count = 0
    skipped_count = 0
    embed_failures = 0

    for idx, entry in enumerate(records):
        title = entry['title']
        if Thesis.objects.filter(title=title).exists():
            skipped_count += 1
            continue

        pdf_bytes = f"Showcase placeholder PDF for: {title}".encode('utf-8')
        sha256 = hashlib.sha256(f'showcase-{idx}-{title}'.encode('utf-8')).hexdigest()

        with transaction.atomic():
            thesis = Thesis(
                title=title,
                abstract=entry['abstract'],
                authors=_authors_for(idx),
                keywords=entry['keywords'],
                program=entry['program'],
                year=entry['year'],
                adviser=_adviser_for(idx),
                file_type=FileType.PDF,
                sha256=sha256,
                extracted_text=f"{title}\n\n{entry['abstract']}",
                status=ThesisStatus.APPROVED,
                uploaded_by=user,
                reviewed_by=user,
                reviewed_at=timezone.now(),
            )
            safe = ''.join(c if c.isalnum() else '_' for c in title)[:60]
            thesis.uploaded_file.save(f'{safe}.pdf', ContentFile(pdf_bytes), save=False)
            thesis.save()

        try:
            generate_thesis_embedding(thesis)
        except Exception as exc:  # pragma: no cover - defensive, embedding is best-effort
            embed_failures += 1
            print(f'  [warn] embedding failed for "{title[:60]}...": {exc}')

        created_count += 1

    total = Thesis.objects.filter(uploaded_by=user).count()
    print(
        f'Showcase seed complete — created {created_count}, skipped {skipped_count} '
        f'(already present), embedding failures {embed_failures}.'
    )
    print(f'Total showcase theses now in DB (uploaded_by={SEED_USER_EMAIL}): {total}')
    for year in (2023, 2024, 2025):
        for program in (BSCS, BSIT, BSIS):
            c = Thesis.objects.filter(uploaded_by=user, year=year, program=program).count()
            print(f'  {year} | {program}: {c}')


main()
