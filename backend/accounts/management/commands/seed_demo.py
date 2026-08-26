from django.core.management.base import BaseCommand

from accounts.models import Team, User, WorkGroup
from tickets.models import Ticket
from tickets.services import create_ticket, resolve_ticket, take_ticket


class Command(BaseCommand):
    help = "Crea la estructura y los usuarios de demostración para desarrollo local."

    password = "Sestel2026!"

    def handle(self, *args, **options):
        tigo, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        contrata, _ = WorkGroup.objects.get_or_create(name="Contrata", defaults={"code": "contrata"})
        bbi, _ = WorkGroup.objects.get_or_create(name="BBI N-2", defaults={"code": "bbi-n2"})

        ftth, _ = Team.objects.get_or_create(group=tigo, name="FTTH Norte", defaults={"code": "ftth-norte"})
        hfc, _ = Team.objects.get_or_create(group=tigo, name="HFC Central", defaults={"code": "hfc-central"})
        Team.objects.get_or_create(group=contrata, name="DTH Occidente", defaults={"code": "dth-occidente"})
        Team.objects.get_or_create(group=bbi, name="Reclamos Norte", defaults={"code": "reclamos-norte"})

        dispatcher = self.upsert_user(
            "despacho@sestel.local",
            "Andrea",
            "Morales",
            User.Role.DISPATCHER,
            ftth,
        )
        support = self.upsert_user(
            "soporte@sestel.local",
            "Mario",
            "Ramírez",
            User.Role.SUPPORT,
            ftth,
        )
        self.upsert_user(
            "admin@sestel.local",
            "Carla",
            "Alvarado",
            User.Role.ADMIN,
            hfc,
            is_staff=True,
        )

        if not Ticket.objects.exists():
            active = create_ticket(
                creator=dispatcher,
                title="ONT sin señal tras activación",
                description="La ONT instalada en la ruta 18 no recibe señal después de completar la activación.",
                category=Ticket.Category.FTTH,
                priority=Ticket.Priority.CRITICAL,
            )
            take_ticket(active, support)

            validation = create_ticket(
                creator=dispatcher,
                title="Validar potencia de fibra en ruta 8",
                description="Se requiere confirmar la potencia óptica después de la visita técnica.",
                category=Ticket.Category.FTTH,
                priority=Ticket.Priority.MEDIUM,
            )
            take_ticket(validation, support)
            resolve_ticket(validation, support, "Se ajustó el conector y la potencia quedó dentro del rango esperado.")

            create_ticket(
                creator=dispatcher,
                title="Intermitencia reportada en nodo HFC 23",
                description="El técnico en campo reporta cortes intermitentes durante la visita.",
                category=Ticket.Category.HFC,
                priority=Ticket.Priority.HIGH,
            )

        self.stdout.write(self.style.SUCCESS("Datos de demostración disponibles."))
        self.stdout.write("Usuarios: despacho@sestel.local, soporte@sestel.local, admin@sestel.local")
        self.stdout.write(f"Contraseña temporal: {self.password}")

    def upsert_user(self, email, first_name, last_name, role, team, is_staff=False):
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.team = team
        user.is_staff = is_staff
        user.is_active = True
        user.set_password(self.password)
        user.save()
        return user
