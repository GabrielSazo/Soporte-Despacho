import uuid

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

SESSION_CLOSED_DETAIL = "Tu sesión se cerró desde otro dispositivo. Inicia sesión de nuevo."


class SessionRefreshToken(RefreshToken):
    """Refresh token que porta el id de sesión vigente del usuario (claim ``sid``)."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token["sid"] = str(user.session_id)
        return token


class SessionJWTAuthentication(JWTAuthentication):
    """Rechaza tokens cuyo ``sid`` no coincida con la sesión vigente del usuario.

    Al hacer login se rota ``User.session_id``: todos los tokens emitidos antes
    (access y refresh) quedan inválidos, incluso si aún no han expirado.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        sid = validated_token.payload.get("sid")
        if sid is None or str(user.session_id) != sid:
            raise AuthenticationFailed(SESSION_CLOSED_DETAIL)
        return user


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    """Valida la sesión vigente antes de rotar el refresh token."""

    token_class = SessionRefreshToken

    def validate(self, attrs):
        try:
            raw = self.token_class(attrs["refresh"])
        except TokenError:
            raise
        sid = raw.payload.get("sid")
        user_id = raw.payload.get(api_settings.USER_ID_CLAIM)
        user = User.objects.filter(pk=user_id).only("session_id").first()
        if user is None or sid is None or str(user.session_id) != sid:
            raise AuthenticationFailed(SESSION_CLOSED_DETAIL)
        return super().validate(attrs)


def rotate_session(user):
    """Emite un nuevo id de sesión e invalida todos los tokens anteriores."""
    user.session_id = uuid.uuid4()
    user.save(update_fields=["session_id"])
    return user
