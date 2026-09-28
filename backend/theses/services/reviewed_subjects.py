"""Count confirmed primary subjects over the published thesis corpus."""

from django.conf import settings

from theses.models import ResearchSubject, Thesis, ThesisStatus


def build_subject_trends():
    subjects = list(ResearchSubject.objects.order_by('sort_order'))
    approved = list(
        Thesis.objects.filter(status=ThesisStatus.APPROVED)
        .only('id', 'title', 'primary_subject', 'subject_reviewed_at')
        .order_by('id')
    )
    members = {subject.code: [] for subject in subjects}
    for thesis in approved:
        if thesis.primary_subject_id and thesis.subject_reviewed_at:
            members[thesis.primary_subject_id].append(thesis)

    reviewed_count = sum(len(group) for group in members.values())
    average = reviewed_count / len(subjects) if subjects else 0
    groups = []
    for subject in subjects:
        theses = members[subject.code]
        count = len(theses)
        if not reviewed_count:
            trend = None
        elif count >= 1.5 * average:
            trend = 'SATURATED'
        elif count <= 0.5 * average:
            trend = 'UNDEREXPLORED'
        else:
            trend = 'EMERGING'
        groups.append({
            'subject_code': subject.code,
            'topic': subject.name,
            'definition': subject.definition,
            'thesis_count': count,
            'trend': trend,
            'thesis_ids': [str(thesis.id) for thesis in theses],
            'sample_titles': [thesis.title for thesis in theses[:3]],
        })

    return {
        'approved_count': len(approved),
        'reviewed_count': reviewed_count,
        'awaiting_review_count': len(approved) - reviewed_count,
        'subjects': groups,
        'saturated_count': sum(group['trend'] == 'SATURATED' for group in groups),
        'emerging_count': sum(group['trend'] == 'EMERGING' for group in groups),
        'underexplored_count': sum(group['trend'] == 'UNDEREXPLORED' for group in groups),
        'main_view_enabled': bool(getattr(settings, 'REVIEWED_SUBJECTS_MAIN_ENABLED', False)),
    }
