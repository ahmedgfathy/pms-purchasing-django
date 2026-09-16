import logging

import ldap
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ActiveDirectoryBackend(ModelBackend):
    """
    Authenticate against Active Directory (PMS.LOCAL at 10.51.0.20:389).
    Only allowed employees can login (checked via EmployeeAccess model).
    Local admin superuser always allowed.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Always allow the local admin superuser
        if username.lower() == "admin":
            try:
                user = User.objects.get(username="admin")
                if user.check_password(password):
                    logger.info("Admin user authenticated locally")
                    return user
            except User.DoesNotExist:
                pass

        # Try AD authentication
        try:
            import django_auth_ldap
            from django_auth_ldap.backend import LDAPBackend

            logger.debug("Attempting AD auth for user: %s", username)

            ldap_backend = LDAPBackend()
            ldap_user = ldap_backend.authenticate(
                request,
                username=username,
                password=password,
            )

            if ldap_user is not None:
                logger.info("AD auth SUCCESS for: %s", username)

                # Get or create Django user
                try:
                    db_user = User.objects.get(username=username)
                except User.DoesNotExist:
                    db_user = User.objects.create_user(
                        username=username,
                        email=getattr(ldap_user, "email", "") or "",
                        first_name=getattr(ldap_user, "first_name", "") or "",
                        last_name=getattr(ldap_user, "last_name", "") or "",
                    )
                    db_user.set_unusable_password()
                    db_user.save()
                    logger.info("Created new AD user in DB: %s", username)

                # Check if employee is allowed to login
                from core.models import EmployeeAccess
                try:
                    access = EmployeeAccess.objects.get(employee_id=username)
                    if not access.is_active:
                        logger.warning("Employee %s exists but is inactive", username)
                        return None
                    logger.info("Employee %s access verified", username)
                    return db_user
                except EmployeeAccess.DoesNotExist:
                    # If no EmployeeAccess record, check if auto_create is enabled
                    # For now, deny access - employee must be added by admin
                    logger.warning(
                        "Employee %s has no access record. "
                        "Ask admin to add them in Django admin > Employee Access.",
                        username,
                    )
                    return None
            else:
                logger.warning("AD auth FAILED for: %s (wrong credentials or AD unreachable)", username)

        except Exception as e:
            logger.error("AD authentication error for %s: %s", username, e, exc_info=True)

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
