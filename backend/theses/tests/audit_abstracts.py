"""Read-only local corpus audit; does not submit uploads or access the database.

Run from backend: python theses/tests/audit_abstracts.py OUTPUT.json CORPUS_ROOT
The root contains the 2021, 2023, 2024 and 2025 source folders.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
import django
django.setup()

from django.db import connections
from theses.views import ThesisExtractMetadataView
from theses.services.text_extractor import ThesisTextExtractor
from theses.services import abstract_recovery


def audit(output, root):
    def no_database(*args, **kwargs):
        raise AssertionError('The metadata audit must never access the database')

    for connection in connections.all():
        connection.ensure_connection = no_database
    results = json.loads(output.read_text(encoding='utf-8')) if output.exists() else []
    completed = {row['document'] for row in results}
    for path in sorted(p for year in ('2021', '2023', '2024', '2025')
                       for p in (root / year).iterdir()
                       if p.suffix.lower() in ('.pdf', '.docx')):
        if str(path.relative_to(root)) in completed:
            continue
        calls = []
        recovery = []
        original = ThesisTextExtractor.extract

        def record(instance, file_path, *, max_pages=None):
            calls.append(max_pages)
            return original(instance, file_path, max_pages=max_pages)

        start = time.monotonic()
        def track(name, function):
            def wrapped(*args, **kwargs):
                found = function(*args, **kwargs)
                if found[0]:
                    recovery.append(name)
                return found
            return wrapped

        with ExitStack() as stack:
            stack.enter_context(patch.object(ThesisTextExtractor, 'extract', record))
            for name in ('recover_text_abstract', 'recover_layout_abstract', 'recover_ocr_abstract'):
                stack.enter_context(patch.object(abstract_recovery, name,
                    track(name, getattr(abstract_recovery, name))))
            response = ThesisExtractMetadataView()._extract_and_respond(str(path))
        row = dict(document=str(path.relative_to(root)),
                   sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   status=response.status_code, response=response.data,
                   extraction_page_limits=calls,
                   recovery=recovery,
                   seconds=round(time.monotonic() - start, 3))
        results.append(row)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        abstract = response.data.get('fields', {}).get('abstract', {})
        print(path.name, len(abstract.get('value', '')), abstract.get('confidence'), flush=True)


if __name__ == '__main__':
    audit(Path(sys.argv[1]), Path(sys.argv[2]))
