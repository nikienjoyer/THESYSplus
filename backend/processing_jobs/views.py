from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProcessingJob


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        # A job ID alone is never a capability. Other users see the same 404 as
        # a nonexistent job.
        try:
            job = ProcessingJob.objects.get(id=job_id, owner=request.user)
        except ProcessingJob.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = {'id': str(job.id), 'state': job.state, 'kind': job.kind}
        if job.state == ProcessingJob.State.SUCCEEDED:
            data['result'] = job.result
        elif job.state == ProcessingJob.State.FAILED:
            data['error'] = job.error
        return Response(data)
