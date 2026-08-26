from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CurrentUserView, EmailTokenObtainPairView, LogoutView, PasswordResetConfirmView, PasswordResetRequestView, PublicPasswordResetView, TeamViewSet, UserViewSet, WorkGroupViewSet


router = DefaultRouter()
router.register("groups", WorkGroupViewSet, basename="group")
router.register("teams", TeamViewSet, basename="team")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", CurrentUserView.as_view(), name="current_user"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("", include(router.urls)),
]
