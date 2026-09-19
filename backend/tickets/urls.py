from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DashboardView, EscalationAreaViewSet, ReportsExportView, ReportsSummaryView, RequestTypeViewSet, TicketViewSet


router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("request-types", RequestTypeViewSet, basename="request-type")
router.register("escalation-areas", EscalationAreaViewSet, basename="escalation-area")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/summary/", ReportsSummaryView.as_view(), name="reports-summary"),
    path("reports/export/", ReportsExportView.as_view(), name="reports-export"),
] + router.urls