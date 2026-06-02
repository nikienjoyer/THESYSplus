"""DRF serializers for the theses app — Phase 1.

* ``ThesisUploadSerializer`` — validates the multipart upload payload.
* ``ThesisListItemSerializer`` — compact card data for the repository list.
* ``ThesisDetailSerializer`` — full record for the detail view.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import Program, Thesis


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class ThesisUploadSerializer(serializers.Serializer):
    """Validates the upload payload (file is validated separately)."""

    title = serializers.CharField(min_length=5, max_length=500, allow_blank=False)
    abstract = serializers.CharField(min_length=20, max_length=10_000, allow_blank=False)
    authors = serializers.ListField(
        child=serializers.CharField(max_length=160, allow_blank=False),
        min_length=1,
        max_length=10,
    )
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=80, allow_blank=False),
        min_length=1,
        max_length=20,
    )
    program = serializers.ChoiceField(choices=[p.value for p in Program])
    year = serializers.IntegerField(min_value=1980, max_value=2100)
    adviser = serializers.CharField(max_length=160, required=False, allow_blank=True, default='')

    def validate_authors(self, value):
        cleaned = [a.strip() for a in value if a and a.strip()]
        if not cleaned:
            raise serializers.ValidationError('At least one author is required.')
        return cleaned

    def validate_keywords(self, value):
        cleaned = [k.strip() for k in value if k and k.strip()]
        if not cleaned:
            raise serializers.ValidationError('At least one keyword is required.')
        return cleaned


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class ThesisListItemSerializer(serializers.ModelSerializer):
    """Compact card shape for ``GET /theses/``."""

    uploaded_by_name = serializers.SerializerMethodField()
    similarity_score = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Thesis
        fields = (
            'id',
            'title',
            'authors',
            'keywords',
            'program',
            'year',
            'adviser',
            'status',
            'file_type',
            'uploaded_by_name',
            'created_at',
            'similarity_score',
        )
        read_only_fields = fields

    def get_uploaded_by_name(self, obj) -> str:
        u = obj.uploaded_by
        if not u:
            return ''
        full = f'{u.first_name} {u.last_name}'.strip()
        return full or u.email


class ThesisDetailSerializer(serializers.ModelSerializer):
    """Full thesis record for ``GET /theses/{id}/``."""

    uploaded_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Thesis
        fields = (
            'id',
            'title',
            'abstract',
            'authors',
            'keywords',
            'program',
            'year',
            'adviser',
            'status',
            'file_type',
            'sha256',
            'embedding_status',
            'rejection_reason',
            'uploaded_by_name',
            'reviewed_at',
            'created_at',
            'updated_at',
            'download_url',
        )
        read_only_fields = fields

    def get_uploaded_by_name(self, obj) -> str:
        u = obj.uploaded_by
        if not u:
            return ''
        full = f'{u.first_name} {u.last_name}'.strip()
        return full or u.email

    def get_download_url(self, obj) -> str:
        return f'/api/v1/theses/{obj.id}/download/'
