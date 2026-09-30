from django.db import migrations

# Title case, with "and" kept lowercase.
NAMES = {
    'EDU': ('Education and learning', 'Education and Learning'),
    'ACA': ('Academic services and research', 'Academic Services and Research'),
    'AGR': ('Agriculture and growing systems', 'Agriculture and Growing Systems'),
    'HEA': ('Health and medicine', 'Health and Medicine'),
    'PUB': ('Public and community services', 'Public and Community Services'),
    'COM': ('Commerce and marketplaces', 'Commerce and Marketplaces'),
    'HOU': ('Housing and accommodation', 'Housing and Accommodation'),
    'TRA': ('Transportation and mobility', 'Transportation and Mobility'),
    'SEC': ('Safety and security', 'Safety and Security'),
    'ACC': ('Accessibility and assistive technology', 'Accessibility and Assistive Technology'),
    'WOR': ('Careers and placements', 'Careers and Placements'),
    'PER': ('Everyday life and productivity', 'Everyday Life and Productivity'),
}


def _rename(apps, schema_editor, index):
    Subject = apps.get_model('theses', 'ResearchSubject')
    db = schema_editor.connection.alias
    for code, names in NAMES.items():
        Subject.objects.using(db).filter(code=code).update(name=names[index])


class Migration(migrations.Migration):
    dependencies = [('theses', '0008_remove_act_program')]

    operations = [
        migrations.RunPython(
            lambda apps, se: _rename(apps, se, 1),
            lambda apps, se: _rename(apps, se, 0),
        ),
    ]
