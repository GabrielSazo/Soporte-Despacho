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


class HasDashboardAccess(BasePermission):
    """El panel de resumen pertenece a los perfiles operativos que lo tienen en su navegación
    (ADMIN, SUPERVISOR y SOPORTE). El DESPACHADOR no cuenta con esa vista."""

    message = "Tu perfil no tiene acceso al panel de resumen."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in (user.Role.ADMIN, user.Role.SUPERVISOR, user.Role.SUPPORT)
        )