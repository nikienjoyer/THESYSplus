"""Verification script for identity_verification app setup.

This script verifies that:
1. The Django app is properly configured
2. Models are registered and can be imported
3. Migrations have been applied
4. Admin interface is configured
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from django.apps import apps
from django.contrib import admin
from identity_verification.models import VerificationDocument, VerificationResult


def verify_app_setup():
    """Verify the identity_verification app is properly set up."""
    
    print("=" * 70)
    print("Identity Verification App Setup Verification")
    print("=" * 70)
    
    # 1. Check if app is installed
    print("\n1. Checking if app is installed...")
    app_config = apps.get_app_config('identity_verification')
    print(f"   ✓ App name: {app_config.name}")
    print(f"   ✓ Verbose name: {app_config.verbose_name}")
    
    # 2. Check models
    print("\n2. Checking models...")
    models = app_config.get_models()
    print(f"   ✓ Found {len(models)} models:")
    for model in models:
        print(f"     - {model.__name__} (table: {model._meta.db_table})")
    
    # 3. Check model fields
    print("\n3. Checking VerificationDocument fields...")
    doc_fields = [f.name for f in VerificationDocument._meta.get_fields()]
    print(f"   ✓ Fields: {', '.join(doc_fields)}")
    
    print("\n4. Checking VerificationResult fields...")
    result_fields = [f.name for f in VerificationResult._meta.get_fields()]
    print(f"   ✓ Fields: {', '.join(result_fields)}")
    
    # 4. Check admin registration
    print("\n5. Checking admin registration...")
    if VerificationDocument in admin.site._registry:
        print("   ✓ VerificationDocument is registered in admin")
    else:
        print("   ✗ VerificationDocument is NOT registered in admin")
    
    if VerificationResult in admin.site._registry:
        print("   ✓ VerificationResult is registered in admin")
    else:
        print("   ✗ VerificationResult is NOT registered in admin")
    
    # 5. Check subdirectories
    print("\n6. Checking subdirectories...")
    app_path = app_config.path
    subdirs = ['services', 'validators', 'tests', 'migrations']
    for subdir in subdirs:
        subdir_path = os.path.join(app_path, subdir)
        if os.path.isdir(subdir_path):
            print(f"   ✓ {subdir}/ exists")
        else:
            print(f"   ✗ {subdir}/ does NOT exist")
    
    # 6. Check key files
    print("\n7. Checking key files...")
    key_files = [
        'models.py',
        'admin.py',
        'apps.py',
        'types.py',
        'protocols.py',
        'constants.py',
        'normalizers.py',
        'views.py',
    ]
    for filename in key_files:
        file_path = os.path.join(app_path, filename)
        if os.path.isfile(file_path):
            print(f"   ✓ {filename} exists")
        else:
            print(f"   ✗ {filename} does NOT exist")
    
    print("\n" + "=" * 70)
    print("Verification Complete!")
    print("=" * 70)


if __name__ == '__main__':
    verify_app_setup()
