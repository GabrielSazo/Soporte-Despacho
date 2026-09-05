from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Team, User, WorkGroup


@admin.register(WorkGroup)
class WorkGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "code", "is_active")
    list_filter = ("group", "is_active")
    search_fields = ("name", "code")


@admin.register(User)
class SestelUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Operación", {"fields": ("role", "teams", "managed_groups", "last_assigned_at")}),)
    filter_horizontal = ("teams", "managed_groups")

    def get_teams(self, obj):
        teams = ", ".join(t.name for t in obj.teams.all())
        mgroups = ", ".join(g.name for g in obj.managed_groups.all())
        if mgroups:
            return f"{teams} | Supervisa: {mgroups}" if teams else f"Supervisa: {mgroups}"
        return teams or "-"
    get_teams.short_description = "Equipos / Supervisión"

    list_display = ("username", "email", "first_name", "last_name", "role", "get_teams", "is_active")
    list_filter = ("role", "is_active")
