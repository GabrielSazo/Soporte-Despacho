from django.core.management.base import BaseCommand

from accounts.models import Team, User, WorkGroup
from tickets.models import Ticket
from tickets.services import create_ticket, resolve_ticket, take_ticket


class Command(BaseCommand):
    help = "Crea la estructura y los usuarios de demostración para desarrollo local."

    password = "Sestel2026!"

    def handle(self, *args, **options):
        tigo, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        bbi, _ = WorkGroup.objects.get_or_create(name="BBI N-2", defaults={"code": "bbi-n2"})
        celtech, _ = WorkGroup.objects.get_or_create(name="celtech", defaults={"code": "celtech"})
        cellus, _ = WorkGroup.objects.get_or_create(name="cellus", defaults={"code": "cellus"})
        nexel, _ = WorkGroup.objects.get_or_create(name="nexel", defaults={"code": "nexel"})

        # Tigo: 14 estaciones
        estaciones = []
        for i in range(1, 15):
            team, _ = Team.objects.get_or_create(group=tigo, name=f"Estacion {i}", defaults={"code": f"estacion{i}"})
            estaciones.append(team)
        estacion1 = estaciones[0]
        estacion2 = estaciones[1] if len(estaciones) > 1 else estacion1

        soporte_n2, _ = Team.objects.get_or_create(group=bbi, name="Soporte-N2", defaults={"code": "reclamos"})
        Team.objects.get_or_create(group=celtech, name="Celtech", defaults={"code": "celtech"})
        Team.objects.get_or_create(group=cellus, name="Cellus", defaults={"code": "cellus"})
        Team.objects.get_or_create(group=nexel, name="Nexel", defaults={"code": "nexel"})

        dispatcher = self.upsert_user(
            "despacho@sestel.local",
            "Andrea",
            "Morales",
            User.Role.DISPATCHER,
            [estacion1, estacion2],
        )
        support = self.upsert_user(
            "soporte@sestel.local",
            "Mario",
            "Ramírez",
            User.Role.SUPPORT,
            [estacion1, estacion2],
        )
        self.upsert_user(
            "admin@sestel.local",
            "Carla",
            "Alvarado",
            User.Role.ADMIN,
            [estacion1, estacion2],
            is_staff=True,
        )
        supervisor = self.upsert_user(
            "supervisor@sestel.local",
            "Luis",
            "González",
            User.Role.SUPERVISOR,
            [],  # sin equipos, solo grupo supervisado
            managed_groups=[tigo],
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
        self.stdout.write("Usuarios: despacho@sestel.local, soporte@sestel.local, admin@sestel.local, supervisor@sestel.local")
        self.stdout.write(f"Contraseña temporal: {self.password}")

    def upsert_user(self, email, first_name, last_name, role, teams, is_staff=False, managed_groups=None):
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_staff = is_staff
        user.is_active = True
        user.set_password(self.password)
        user.save()
        user.teams.set(teams)
        if managed_groups is not None:
            user.managed_groups.set(managed_groups)
        return user
