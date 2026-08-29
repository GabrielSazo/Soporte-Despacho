from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = kwargs.get("email") or username
        if not identifier or not password:
            return None

        user_model = get_user_model()
        try:
            user = user_model.objects.get(Q(username__iexact=identifier) | Q(email__iexact=identifier))
        except user_model.DoesNotExist:
            user_model().set_password(password)
            return None

        if user.is_account_locked:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            if user.failed_login_attempts or user.locked_at:
                user.reset_login_attempts()
            return user

        # Contraseña incorrecta: registrar intento
        user.record_failed_login()
        return None
