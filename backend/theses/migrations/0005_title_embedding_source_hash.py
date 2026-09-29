from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('theses', '0004_research_subject_review')]

    operations = [
        migrations.AddField(
            model_name='thesis',
            name='title_embedding_source_hash',
            field=models.CharField(max_length=64, blank=True, default=''),
        ),
    ]
