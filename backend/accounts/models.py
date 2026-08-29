from django.contrib.auth.models import AbstractUser
from django.db import models


class WorkGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "grupo"
        verbose_name_plural = "grupos"

    def __str__(self):
        return self.name


class Team(models.Model):
    group = models.ForeignKey(WorkGroup, on_delete=models.PROTECT, related_name="teams")
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["group__name", "name"]
        constraints = [models.UniqueConstraint(fields=["group", "name"], name="unique_team_name_per_group")]
        verbose_name = "equipo"
        verbose_name_plural = "equipos"

    def __str__(self):
        return f"{self.group.name} - {self.name}"


class User(AbstractUser):
    class Role(models.TextChoices):
        DISPATCHER = "DESPACHADOR", "Despachador"
        SUPPORT = "SOPORTE", "Agente de soporte"
        ADMIN = "ADMIN", "Administrador"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DISPATCHER)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="members", null=True, blank=True)
    last_assigned_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)

    @property
    def group(self):
        return self.team.group if self.team_id else None

    @property
    def display_name(self):
        name = self.get_full_name().strip()
        return name or self.username

    @property
    def is_account_locked(self):
        return self.failed_login_attempts >= 5 or self.locked_at is not None

    @property
    def is_administrator(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    def record_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from django.utils import timezone
            self.locked_at = timezone.now()
        self.save(update_fields=["failed_login_attempts", "locked_at"])

    def reset_login_attempts(self):
        if self.failed_login_attempts or self.locked_at:
            self.failed_login_attempts = 0
            self.locked_at = None
            self.save(update_fields=["failed_login_attempts", "locked_at"])

    def unlock_via_password_reset(self):
        self.failed_login_attempts = 0
        self.locked_at = None
        self.save(update_fields=["failed_login_attempts", "locked_at"])
