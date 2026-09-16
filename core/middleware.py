from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class EmployeeAccessMiddleware:
    """
    Check if authenticated user has an EmployeeAccess record.
    Redirect to login if not allowed.
    """

    EXEMPT_URLS = [
        "login",
        "logout",
        "set_language",
        "admin:index",
        "admin:login",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Admin superuser bypasses all checks
            if request.user.is_superuser:
                return self.get_response(request)

            url_name = request.resolver_match.url_name if request.resolver_match else ""
            namespace = request.resolver_match.namespace if request.resolver_match else ""

            # Skip check for exempt URLs
            if url_name in self.EXEMPT_URLS or namespace == "admin":
                return self.get_response(request)

            # Check if user has EmployeeAccess
            from core.models import EmployeeAccess
            try:
                access = EmployeeAccess.objects.get(
                    employee_id=request.user.username,
                    is_active=True,
                )
                request.employee_access = access
            except EmployeeAccess.DoesNotExist:
                # No access record - deny and redirect
                from django.contrib import messages
                messages.error(
                    request,
                    "Access denied. Contact administrator to request access.",
                )
                return redirect("login")

        response = self.get_response(request)
        return response
