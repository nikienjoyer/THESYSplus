"""Read-only request history with per-request, service-backed decisions."""

from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from accounts.models import Role

from .models import AccessRequest
from .services import (
    AccessRequestEmailCollision,
    AccessRequestNotPending,
    approve_request,
    deny_request,
)


class _ApproveAccessRequestForm(forms.Form):
    note = forms.CharField(
        label='Review note',
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Optional note saved with the request review.',
    )


class _DenyAccessRequestForm(forms.Form):
    reason = forms.CharField(
        label='Reason for rejection',
        required=True,
        min_length=1,
        max_length=2000,
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text='This reason is recorded and included in the applicant notification.',
    )


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    """Expose requests and their history without allowing direct field edits."""

    change_form_template = 'admin/access_requests/accessrequest/change_form.html'
    actions = None

    list_display = (
        'requester',
        'email',
        'requested_role',
        'status',
        'created_at',
        'reviewed_by',
        'reviewed_at',
        'review_note_preview',
    )
    list_filter = ('status', 'requested_role', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50
    list_select_related = ('reviewed_by',)

    fields = (
        'id',
        'first_name',
        'last_name',
        'email',
        'requested_role',
        'justification',
        'status',
        'created_at',
        'verification_document_link',
        'verification_result_link',
        'review_note',
        'reviewed_by',
        'reviewed_at',
    )
    readonly_fields = fields

    @admin.display(description='Requester', ordering='last_name')
    def requester(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()

    @admin.display(description='Review note')
    def review_note_preview(self, obj):
        if not obj.review_note:
            return '—'
        return format_html('{}', obj.review_note[:100] + ('…' if len(obj.review_note) > 100 else ''))

    @admin.display(description='Verification document id')
    def verification_document_link(self, obj):
        try:
            document = obj.verification_document
        except ObjectDoesNotExist:
            return '—'
        url = reverse(
            'admin:identity_verification_verificationdocument_change',
            args=(document.pk,),
        )
        return format_html('<a href="{}">{}</a>', url, document.pk)

    @admin.display(description='Verification result id')
    def verification_result_link(self, obj):
        try:
            result = obj.verification_result
        except ObjectDoesNotExist:
            return '—'
        url = reverse(
            'admin:identity_verification_verificationresult_change',
            args=(result.pk,),
        )
        return format_html('<a href="{}">{}</a>', url, result.pk)

    @staticmethod
    def _is_staff_administrator(request):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.is_staff
            and getattr(user, 'role', None) == Role.ADMINISTRATOR
        )

    def has_module_permission(self, request):
        return self._is_staff_administrator(request)

    def has_view_permission(self, request, obj=None):
        return self._is_staff_administrator(request)

    def has_change_permission(self, request, obj=None):
        return self._is_staff_administrator(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('reviewed_by')

    def get_urls(self):
        custom_urls = [
            path(
                '<uuid:object_id>/approve/',
                self.admin_site.admin_view(self.approve_request_view),
                name='access_requests_accessrequest_approve',
            ),
            path(
                '<uuid:object_id>/reject/',
                self.admin_site.admin_view(self.reject_request_view),
                name='access_requests_accessrequest_reject',
            ),
        ]
        return custom_urls + super().get_urls()

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj is not None and obj.status == 'pending':
            context['approve_url'] = reverse(
                'admin:access_requests_accessrequest_approve', args=(obj.pk,),
            )
            context['reject_url'] = reverse(
                'admin:access_requests_accessrequest_reject', args=(obj.pk,),
            )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def approve_request_view(self, request, object_id):
        return self._review_request(request, object_id, decision='approve')

    def reject_request_view(self, request, object_id):
        return self._review_request(request, object_id, decision='reject')

    def _review_request(self, request, object_id, *, decision):
        if not self._is_staff_administrator(request):
            raise PermissionDenied

        access_request = self.get_object(request, str(object_id))
        if access_request is None:
            raise Http404('Access request not found.')

        change_url = reverse(
            'admin:access_requests_accessrequest_change', args=(access_request.pk,),
        )
        if access_request.status != 'pending':
            self.message_user(
                request,
                'Only pending requests can be approved or rejected.',
                level=messages.WARNING,
            )
            return HttpResponseRedirect(change_url)

        approve = decision == 'approve'
        form_class = _ApproveAccessRequestForm if approve else _DenyAccessRequestForm
        form = form_class(request.POST or None)

        if request.method == 'POST' and form.is_valid():
            try:
                if approve:
                    approve_request(
                        access_request,
                        reviewer=request.user,
                        note=form.cleaned_data['note'],
                        request=request,
                    )
                else:
                    deny_request(
                        access_request,
                        reviewer=request.user,
                        reason=form.cleaned_data['reason'],
                        request=request,
                    )
            except AccessRequestNotPending:
                self.message_user(
                    request,
                    'This request was already reviewed. Its current status is shown below.',
                    level=messages.WARNING,
                )
                return HttpResponseRedirect(change_url)
            except AccessRequestEmailCollision:
                self.message_user(
                    request,
                    'An account already exists for this email. The request was not approved.',
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(change_url)

            self.message_user(
                request,
                'Access request approved and account activation initiated.'
                if approve else 'Access request rejected.',
                level=messages.SUCCESS,
            )
            return HttpResponseRedirect(change_url)

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'original': access_request,
            'title': 'Approve access request' if approve else 'Reject access request',
            'form': form,
            'submit_label': 'Approve request' if approve else 'Reject request',
            'cancel_url': change_url,
            'requester_name': f'{access_request.first_name} {access_request.last_name}'.strip(),
            'requested_role': access_request.get_requested_role_display(),
            'decision': decision,
        }
        return TemplateResponse(
            request,
            'admin/access_requests/accessrequest/confirm_review.html',
            context,
        )
