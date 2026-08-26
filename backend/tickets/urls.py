from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DashboardView, TicketViewSet


router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [path("dashboard/", DashboardView.as_view(), name="dashboard")] + router.urls
