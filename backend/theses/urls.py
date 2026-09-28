"""URL configuration for the theses app — Phase 1.

Mounted at ``/api/v1/theses/`` by ``thesys/urls.py``.
"""

from django.urls import path

from .views import (
    ThesisAnalyticsView,
    ResearchSubjectListView,
    ThesisDetailView,
    ThesisDownloadView,
    ThesisExtractMetadataView,
    ThesisExtractTitleView,
    ThesisListView,
    ThesisPublicStatsView,
    ThesisSearchView,
    ThesisTopicTrendsView,
    ThesisSubjectTrendsView,
    ThesisSubjectReviewView,
    ThesisUploadView,
    ThesisValidateTitleView,
)

urlpatterns = [
    path('', ThesisListView.as_view(), name='thesis-list'),
    path('public-stats/', ThesisPublicStatsView.as_view(), name='thesis-public-stats'),
    path('upload/', ThesisUploadView.as_view(), name='thesis-upload'),
    path('search/', ThesisSearchView.as_view(), name='thesis-search'),
    path('validate-title/', ThesisValidateTitleView.as_view(), name='thesis-validate-title'),
    path('extract-title/', ThesisExtractTitleView.as_view(), name='thesis-extract-title'),
    path('extract-metadata/', ThesisExtractMetadataView.as_view(), name='thesis-extract-metadata'),
    path('topic-trends/', ThesisTopicTrendsView.as_view(), name='thesis-topic-trends'),
    path('subject-trends/', ThesisSubjectTrendsView.as_view(), name='thesis-subject-trends'),
    path('subjects/', ResearchSubjectListView.as_view(), name='research-subjects'),
    path('analytics/', ThesisAnalyticsView.as_view(), name='thesis-analytics'),
    path('<str:id>/', ThesisDetailView.as_view(), name='thesis-detail'),
    path('<str:id>/download/', ThesisDownloadView.as_view(), name='thesis-download'),
    path('<str:id>/subject/', ThesisSubjectReviewView.as_view(), name='thesis-subject-review'),
]
