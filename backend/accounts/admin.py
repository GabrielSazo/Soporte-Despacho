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
    fieldsets = UserAdmin.fieldsets + (("Operación", {"fields": ("role", "team", "last_assigned_at")}),)
    list_display = ("username", "email", "first_name", "last_name", "role", "team", "is_active")
    list_filter = ("role", "team", "is_active")
