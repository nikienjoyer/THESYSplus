"""Management command — seed 15 demo theses for capstone presentation.

Usage:
    python manage.py seed_theses
    python manage.py seed_theses --reset

Creates a system 'seed-bot@pampangastateu.edu.ph' user (faculty role) as
the uploader so all seeded theses land in 'approved' status. Each thesis
gets a tiny synthetic PDF generated on the fly so the file column,
sha256, and download endpoint all work.
"""

from __future__ import annotations

import hashlib
import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus


SEED_USER_EMAIL = 'seed-bot@pampangastateu.edu.ph'


# ── 15 representative CCS theses ─────────────────────────────────────────
SAMPLE_THESES = [
    {
        'title': 'AI-Powered Attendance Monitoring Using Facial Recognition for PSU Classrooms',
        'abstract': 'This study proposes a deep-learning attendance system that uses MTCNN for face detection and ArcFace embeddings for identification, integrated with a Django dashboard for instructors. Field tests show 96.4% accuracy across varied lighting conditions in PSU CCS classrooms.',
        'authors': ['Dela Cruz, Juan M.', 'Santos, Maria L.'],
        'keywords': ['facial recognition', 'attendance', 'deep learning', 'ArcFace', 'AI'],
        'program': Program.BSIT.value,
        'year': 2024,
        'adviser': 'Prof. Reyes, Roberto',
    },
    {
        'title': 'Internet of Things (IoT) Greenhouse Monitoring System with Real-Time Data Visualization',
        'abstract': 'An ESP32-based greenhouse environmental monitoring solution measuring temperature, humidity, soil moisture, and light intensity. Data is streamed via MQTT to a Node-RED dashboard with predictive alerts.',
        'authors': ['Reyes, Pedro A.', 'Garcia, Ana B.', 'Lopez, Carlos D.'],
        'keywords': ['IoT', 'ESP32', 'MQTT', 'agriculture', 'sensors'],
        'program': Program.BSIT.value,
        'year': 2023,
        'adviser': 'Engr. Mendoza, Luis',
    },
    {
        'title': 'A Hybrid Recommendation System for Academic Research Papers Using Collaborative Filtering and Content-Based Filtering',
        'abstract': 'Implements a hybrid recommender combining matrix factorization with TF-IDF cosine similarity over abstracts. Evaluated on 5,000 PSU thesis records with offline metrics RMSE 0.87 and MAP@10 of 0.71.',
        'authors': ['Mendoza, Luis E.', 'Torres, Rosa F.'],
        'keywords': ['recommender systems', 'collaborative filtering', 'TF-IDF', 'NLP', 'research'],
        'program': Program.BSCS.value,
        'year': 2024,
        'adviser': 'Dr. Villanueva, Carmen',
    },
    {
        'title': 'Web-Based Inventory Management System for Small Retail Businesses with Sales Forecasting',
        'abstract': 'A Laravel + Vue.js inventory web app integrated with an ARIMA-based monthly demand forecast module. Pilot tested with three sari-sari stores in San Fernando, reducing stockouts by 38%.',
        'authors': ['Villanueva, Carmen P.', 'Cruz, Antonio R.'],
        'keywords': ['web system', 'inventory', 'ARIMA', 'forecasting', 'Laravel'],
        'program': Program.BSIS.value,
        'year': 2022,
        'adviser': 'Prof. Tan, Miguel',
    },
    {
        'title': 'Mobile-Based Health Monitoring Application for Hypertension Patients Using Wearable Devices',
        'abstract': 'A Flutter app paired with a Bluetooth blood-pressure cuff that logs readings, computes 7-day trends, and sends alerts to a designated physician. HIPAA-aligned data encryption is implemented at rest and in transit.',
        'authors': ['Tan, Miguel S.', 'Aquino, Bernadette J.'],
        'keywords': ['mobile health', 'wearable', 'hypertension', 'Flutter', 'Bluetooth'],
        'program': Program.BSIT.value,
        'year': 2023,
        'adviser': 'Dr. Ramos, Patricia',
    },
    {
        'title': 'Educational Technology Platform for Adaptive Mathematics Learning in Senior High School',
        'abstract': 'An adaptive learning system that uses item response theory to estimate student ability and serve personalised problem sets. A 12-week classroom trial showed a 21% gain in standardized math scores.',
        'authors': ['Aquino, Bernadette J.', 'Ramos, Patricia C.'],
        'keywords': ['educational technology', 'adaptive learning', 'IRT', 'mathematics'],
        'program': Program.BSIS.value,
        'year': 2024,
        'adviser': 'Prof. Bautista, Jose',
    },
    {
        'title': 'Convolutional Neural Network for Tagalog Handwritten Digit Recognition on Mobile Devices',
        'abstract': 'A lightweight 4-layer CNN (TFLite) for digit recognition in handwritten Tagalog student worksheets. Achieves 98.1% test accuracy with 3.2 MB model size suitable for mid-range Android devices.',
        'authors': ['Ramos, Patricia C.'],
        'keywords': ['CNN', 'OCR', 'Tagalog', 'mobile', 'TFLite'],
        'program': Program.BSCS.value,
        'year': 2025,
        'adviser': 'Dr. Sy, Christopher',
    },
    {
        'title': 'Blockchain-Based Academic Credential Verification System for Pampanga State University',
        'abstract': 'A permissioned Hyperledger Fabric network for issuing and verifying digital diplomas. Integrates with the registrar SIS via REST APIs and supports QR-code on-chain proof retrieval.',
        'authors': ['Sy, Christopher D.', 'Cabrera, Maria E.'],
        'keywords': ['blockchain', 'Hyperledger', 'credentials', 'verification', 'web system'],
        'program': Program.BSIT.value,
        'year': 2025,
        'adviser': 'Prof. Reyes, Roberto',
    },
    {
        'title': 'Real-Time Sign Language Recognition System Using MediaPipe and LSTM Networks',
        'abstract': 'Combines MediaPipe Hands keypoint extraction with a stacked LSTM classifier trained on 30 Filipino Sign Language gestures. Live demo achieves 92% top-1 accuracy at 25 FPS on commodity laptops.',
        'authors': ['Cabrera, Maria E.', 'Lim, Joshua F.'],
        'keywords': ['sign language', 'MediaPipe', 'LSTM', 'AI', 'accessibility'],
        'program': Program.BSCS.value,
        'year': 2024,
        'adviser': 'Dr. Villanueva, Carmen',
    },
    {
        'title': 'Cloud-Based Document Management System with Optical Character Recognition for SMEs',
        'abstract': 'AWS S3 + Lambda backend with a Tesseract OCR pipeline that auto-extracts metadata from scanned invoices. Web client built in React. Reduces manual filing time by 64% in pilot.',
        'authors': ['Lim, Joshua F.', 'Park, Hannah G.'],
        'keywords': ['cloud', 'AWS', 'OCR', 'document management', 'web system'],
        'program': Program.BSIS.value,
        'year': 2023,
        'adviser': 'Engr. Mendoza, Luis',
    },
    {
        'title': 'Sentiment Analysis of Filipino Code-Switched Tweets Using Multilingual BERT',
        'abstract': 'Fine-tunes mBERT on a 12,000-tweet dataset of Tagalog-English code-switched social media posts annotated for sentiment. Achieves macro-F1 of 0.83 on a held-out test set.',
        'authors': ['Park, Hannah G.', 'Bautista, Jose H.'],
        'keywords': ['NLP', 'sentiment analysis', 'BERT', 'code-switching', 'Filipino'],
        'program': Program.BSCS.value,
        'year': 2024,
        'adviser': 'Dr. Sy, Christopher',
    },
    {
        'title': 'Smart Parking System Using Computer Vision and IoT Sensors',
        'abstract': 'A YOLOv5-based vehicle detector running on a Raspberry Pi 4 paired with magnetic sensors per stall. Live availability data is exposed through a public REST API and a mobile app.',
        'authors': ['Bautista, Jose H.', 'Mercado, Daniel I.'],
        'keywords': ['IoT', 'YOLOv5', 'computer vision', 'parking', 'Raspberry Pi'],
        'program': Program.BSIT.value,
        'year': 2022,
        'adviser': 'Prof. Tan, Miguel',
    },
    {
        'title': 'E-Learning Management System Tailored for Computing Studies Curriculum',
        'abstract': 'A Django-based LMS with auto-graded coding exercises (CodeRunner backend), forum integration, and BigBlueButton conferencing. Adopted by three CCS courses with 320 active learners.',
        'authors': ['Mercado, Daniel I.', 'Yap, Sophia J.'],
        'keywords': ['e-learning', 'LMS', 'educational technology', 'Django', 'web system'],
        'program': Program.BSIS.value,
        'year': 2021,
        'adviser': 'Dr. Ramos, Patricia',
    },
    {
        'title': 'Computer-Assisted Diagnosis of Diabetic Retinopathy Using Transfer Learning',
        'abstract': 'Compares ResNet50, EfficientNet-B0, and DenseNet121 fine-tuned on the APTOS 2019 retinal image dataset. EfficientNet-B0 achieves the best validation kappa of 0.91.',
        'authors': ['Yap, Sophia J.'],
        'keywords': ['health monitoring', 'transfer learning', 'EfficientNet', 'medical imaging'],
        'program': Program.BSCS.value,
        'year': 2025,
        'adviser': 'Dr. Sy, Christopher',
    },
    {
        'title': 'Associate Computer Technology Lab Equipment Tracking System',
        'abstract': 'A QR-coded asset tracking system for ACT lab consumables and PCs, with check-in/check-out workflows, low-stock alerts, and a monthly utilization report.',
        'authors': ['Navarro, Kim L.', 'Alarcon, Faith M.'],
        'keywords': ['inventory', 'QR code', 'web system', 'asset tracking'],
        'program': Program.ACT.value,
        'year': 2023,
        'adviser': 'Prof. Bautista, Jose',
    },
]


def _build_minimal_pdf(title: str, abstract: str) -> bytes:
    """Create a tiny, valid one-page PDF carrying the title + abstract."""
    safe_title = title.replace('(', '\\(').replace(')', '\\)')
    safe_abstract = abstract.replace('(', '\\(').replace(')', '\\)')
    body_text = f'TITLE: {safe_title}\\nABSTRACT: {safe_abstract}'
    # Minimal PDF 1.4 — 4 objects: catalog, pages, page, content stream
    content = f'BT /F1 12 Tf 50 750 Td ({body_text}) Tj ET'.encode('latin-1', errors='replace')
    parts = []
    parts.append(b'%PDF-1.4\n')
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
        + content
        + b'\nendstream endobj\n'
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


class Command(BaseCommand):
    help = 'Seed the THESYS+ repository with demo theses for capstone presentation.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing seeded theses before re-seeding.',
        )

    def handle(self, *args, **options):
        # Step 1: ensure seed user exists (faculty role → uploads land 'approved')
        user, created = User.objects.get_or_create(
            email=SEED_USER_EMAIL,
            defaults={
                'first_name': 'THESYS+',
                'last_name': 'Seed Bot',
                'role': Role.FACULTY,
                'is_active': True,
                'is_email_verified': True,
            },
        )
        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created seed user: {SEED_USER_EMAIL}'))

        # Step 2: optional reset
        if options.get('reset'):
            count = Thesis.objects.filter(uploaded_by=user).count()
            Thesis.objects.filter(uploaded_by=user).delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} previously-seeded theses.'))

        # Step 3: insert each thesis (skip duplicates by title)
        created_count = 0
        skipped_count = 0
        for entry in SAMPLE_THESES:
            if Thesis.objects.filter(title=entry['title']).exists():
                skipped_count += 1
                continue

            pdf_bytes = _build_minimal_pdf(entry['title'], entry['abstract'])
            sha256 = hashlib.sha256(pdf_bytes).hexdigest()

            with transaction.atomic():
                thesis = Thesis(
                    title=entry['title'],
                    abstract=entry['abstract'],
                    authors=entry['authors'],
                    keywords=entry['keywords'],
                    program=entry['program'],
                    year=entry['year'],
                    adviser=entry.get('adviser', ''),
                    file_type=FileType.PDF,
                    sha256=sha256,
                    extracted_text=f"{entry['title']}\n\n{entry['abstract']}",
                    embedding_status=EmbeddingStatus.NOT_STARTED,
                    status=ThesisStatus.APPROVED,
                    uploaded_by=user,
                    reviewed_by=user,
                    reviewed_at=timezone.now(),
                )
                # Slugify a safe filename
                safe = ''.join(c if c.isalnum() else '_' for c in entry['title'])[:60]
                thesis.uploaded_file.save(
                    f'{safe}.pdf',
                    ContentFile(pdf_bytes),
                    save=False,
                )
                thesis.save()
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete — created {created_count}, skipped {skipped_count} (already present).'
        ))
