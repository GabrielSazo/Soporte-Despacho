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
from .permissions import IsAdministrator, IsAdminOrSupervisor
from .serializers import CurrentUserSerializer, TeamSerializer, UserSerializer, WorkGroupSerializer

password_reset_token_generator = PasswordResetTokenGenerator()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        if email:
            try:
                user = User.objects.get(email__iexact=email)
                if user.is_account_locked:
                    raise ValidationError(
                        {"detail": "Cuenta bloqueada por 5 intentos fallidos. Usa '¿Olvidaste tu contraseña?' para desbloquearla vía correo."},
                        code="account_locked",
                    )
            except User.DoesNotExist:
                pass
        try:
            data = super().validate(attrs)
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            if isinstance(detail, dict) and "detail" in detail:
                raise
            if email:
                try:
                    u = User.objects.get(email__iexact=email)
                    if u.is_account_locked:
                        raise ValidationError(
                            {"detail": "Cuenta bloqueada por 5 intentos fallidos. Usa '¿Olvidaste tu contraseña?' para desbloquearla vía correo."},
                            code="account_locked",
                        )
                    remaining = 5 - u.failed_login_attempts
                    if remaining <= 2 and remaining > 0:
                        raise ValidationError(
                            {"detail": f"Credenciales inválidas. Te quedan {remaining} intentos antes del bloqueo."},
                            code="invalid",
                        )
                except User.DoesNotExist:
                    pass
            raise
        data["user"] = CurrentUserSerializer(self.user).data
        return data


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class CurrentUserView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentUserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return UserSerializer
        return CurrentUserSerializer

    def perform_update(self, serializer):
        # Solo permite cambiar teams/managed_groups propios
        allowed = {"teams", "managed_groups"}
        data = {k: v for k, v in serializer.validated_data.items() if k in allowed}
        # Actualizar solo esos campos
        user = self.get_object()
        if "teams" in data:
            user.teams.set(data["teams"])
        if "managed_groups" in data:
            user.managed_groups.set(data["managed_groups"])


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

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdministrator()]


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.select_related("group").all()
    serializer_class = TeamSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdministrator()]


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError({"email": "Debes indicar el correo."})
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
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; background: #f3f6ff; border-radius: 12px;">
          <h2 style="color: #001eb4; margin: 0 0 12px;">Hola {user.display_name},</h2>
          <p style="color: #0f1a4a; font-size: 14px; line-height: 1.6;">Recibimos una solicitud para restablecer tu contraseña en <b>Soporte Despacho Tigo</b>.</p>
          <p style="text-align: center; margin: 28px 0;">
            <a href="{reset_link}" style="display: inline-block; padding: 12px 28px; background: #001eb4; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">Restablecer contraseña</a>
          </p>
          <p style="color: #5a658d; font-size: 12px;">Este botón es válido por 1 hora. Si no solicitaste este cambio, ignora este correo.</p>
          <p style="color: #8d97b5; font-size: 11px; word-break: break-all;">Si el botón no funciona, copia este enlace: {reset_link}</p>
        </div>
        """
        message = f"Hola {user.display_name},\n\nRestablece tu contraseña aquí: {reset_link}\n\nVálido por 1 hora."
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False, html_message=html_message)

        response_data = {"detail": "Se envió un correo con instrucciones para restablecer tu contraseña. Revisa tu bandeja de entrada."}
        if settings.DEBUG:
            response_data["debug_token"] = token
            response_data["debug_uid"] = uid
            response_data["debug_link"] = reset_link
        return Response(response_data)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        new_password = request.data.get("new_password") or request.data.get("password") or ""
        if not token or not uid or not new_password:
            raise ValidationError({"detail": "Debes indicar token y nueva contraseña."})
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk)
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
        user.unlock_via_password_reset()
        return Response({"detail": "Contraseña restablecida correctamente. Cuenta desbloqueada. Ya puedes iniciar sesión."})


class PublicPasswordResetView(PasswordResetRequestView):
    pass


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related("teams__group", "managed_groups").all()
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        if self.action in ["partial_update", "update"]:
            return [IsAdminOrSupervisor()]
        return [IsAdministrator()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_administrator:
            return qs
        if user.is_supervisor:
            codes = user.group_codes
            return qs.filter(teams__group__code__in=codes).distinct() | qs.filter(managed_groups__code__in=codes).distinct() | qs.filter(pk=user.pk).distinct()
        codes = user.group_codes
        if codes:
            return qs.filter(teams__group__code__in=codes).distinct() | qs.filter(pk=user.pk).distinct()
        return qs.filter(pk=user.pk)

    def perform_update(self, serializer):
        target = serializer.instance
        requester = self.request.user
        if target.pk == requester.pk and serializer.validated_data.get("is_active") is False:
            raise ValidationError({"is_active": "No puedes desactivar tu propia cuenta."})
        if not requester.is_administrator:
            # Supervisor solo puede tocar usuarios de sus grupos y nunca cuentas ADMIN
            if target.role == User.Role.ADMIN or target.is_superuser:
                raise ValidationError({"detail": "Solo un administrador puede modificar cuentas de administración."})
            target_codes = set(target.teams.values_list("group__code", flat=True)) | set(
                target.managed_groups.values_list("code", flat=True)
            )
            if not (set(requester.group_codes) & target_codes) and target.pk != requester.pk:
                raise ValidationError({"detail": "Solo puedes modificar usuarios de tus grupos."})
            new_role = serializer.validated_data.get("role")
            if new_role == User.Role.ADMIN:
                raise ValidationError({"role": "Solo un administrador puede asignar el rol ADMIN."})
            new_teams = serializer.validated_data.get("teams")
            if new_teams is not None:
                allowed = set(requester.group_codes)
                for team in new_teams:
                    if team.group.code not in allowed:
                        raise ValidationError({"teams": f"Solo puedes asignar grupos que supervisas ({team.group.name})."})
            new_mgroups = serializer.validated_data.get("managed_groups")
            if new_mgroups is not None and new_mgroups:
                raise ValidationError({"managed_groups": "Solo un administrador puede asignar grupos supervisados."})
        serializer.save()