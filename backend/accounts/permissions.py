from rest_framework.permissions import BasePermission


class IsAdministrator(BasePermission):
    message = "Esta acción requiere un perfil de administración."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_administrator)


class IsAdminOrSupervisor(BasePermission):
    message = "Esta acción requiere un perfil de administración o supervisión."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_administrator or user.is_supervisor))