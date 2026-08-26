from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Team, User, WorkGroup
from .permissions import IsAdministrator
from .serializers import CurrentUserSerializer, TeamSerializer, UserSerializer, WorkGroupSerializer

password_reset_token_generator = PasswordResetTokenGenerator()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = CurrentUserSerializer(self.user).data
        return data


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class CurrentUserView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentUserSerializer

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "Se requiere el token de actualización."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except Exception:
            return Response({"detail": "El token no es válido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkGroupViewSet(viewsets.ModelViewSet):
    queryset = WorkGroup.objects.all()
    serializer_class = WorkGroupSerializer
    permission_classes = [IsAdministrator]


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.select_related("group").all()
    serializer_class = TeamSerializer
    permission_classes = [IsAdministrator]


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError({"email": "Debes indicar el correo."})
        # Respuesta genérica para no enumerar usuarios; en demo mostramos detalle si no existe para facilitar pruebas.
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            if settings.DEBUG:
                raise ValidationError({"email": "No existe una cuenta con ese correo."})
            return Response({"detail": "Si el correo existe, recibirás instrucciones para restablecer tu contraseña."})
        if not user.is_active:
            raise ValidationError({"email": "La cuenta está desactivada. Contacta a un administrador."})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
        subject = "Soporte Despacho Tigo - Restablece tu contraseña"
        message = (
            f"Hola {user.display_name},\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña en Soporte Despacho Tigo - Centro de Control.\n"
            f"Usa este enlace para definir una nueva clave (válido por 1 hora):\n\n"
            f"{reset_link}\n\n"
            f"Si no solicitaste este cambio, puedes ignorar este correo.\n"
            f"Este es un correo automático, no respondas a esta dirección."
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

        response_data = {"detail": "Se envió un correo con instrucciones para restablecer tu contraseña. Revisa tu bandeja de entrada."}
        if settings.DEBUG:
            response_data["debug_token"] = token
            response_data["debug_uid"] = uid
            response_data["debug_link"] = reset_link
        return Response(response_data)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        new_password = request.data.get("new_password") or request.data.get("password") or ""
        if not email or not token or not uid or not new_password:
            raise ValidationError({"detail": "Debes indicar correo, token y nueva contraseña."})
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk, email__iexact=email)
        except Exception:
            raise ValidationError({"token": "El enlace no es válido."})
        if not password_reset_token_generator.check_token(user, token):
            raise ValidationError({"token": "El token es inválido o ha expirado. Solicita uno nuevo."})
        if len(new_password) < 8:
            raise ValidationError({"new_password": ["La contraseña debe tener al menos 8 caracteres."]})
        try:
            validate_password(new_password, user=None)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)})
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Contraseña restablecida correctamente. Ya puedes iniciar sesión."})


# Compatibilidad: endpoint anterior que pedía clave directa ahora delega al flujo por correo.
# Se mantiene para no romper el modal administrativo, pero el login usará el flujo por correo.
class PublicPasswordResetView(PasswordResetRequestView):
    pass


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("team__group").all()
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_update(self, serializer):
        target = serializer.instance
        if target.pk == self.request.user.pk and serializer.validated_data.get("is_active") is False:
            raise ValidationError({"is_active": "No puedes desactivar tu propia cuenta."})
        serializer.save()
