from rest_framework.permissions import BasePermission


class IsAdministrator(BasePermission):
    message = "Esta acción requiere un perfil de administración."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_administrator)
