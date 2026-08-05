"""URL placeholder for the ``accounts`` app.

The Foundation Phase intentionally registers no routes here. The root URLConf
includes this module so the ``/api/v1/<...>/`` mount points exist end-to-end.
Real views land in a later phase.
"""

urlpatterns: list = []
