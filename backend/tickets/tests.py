from datetime import timedelta
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Team, User, WorkGroup

from .models import Ticket
from .services import create_ticket, resolve_ticket, take_ticket


class TicketFlowTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))
        group, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        self.team, _ = Team.objects.get_or_create(group=group, name="FTTH Norte", defaults={"code": "ftth-norte"})
        self.soporte_b, _ = Team.objects.get_or_create(
            group=WorkGroup.objects.get(code="soporte-b"), name="Soporte B", defaults={"code": "soporte-b"}
        )
        self.dispatcher = User.objects.create_user(
            username="despacho@sestel.local",
            email="despacho@sestel.local",
            password="Sestel2026!",
            first_name="Andrea",
            last_name="Morales",
            role=User.Role.DISPATCHER,
        )
        self.dispatcher.teams.set([self.team])
        self.other_dispatcher = User.objects.create_user(
            username="otro@sestel.local",
            email="otro@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
        )
        self.other_dispatcher.teams.set([self.team])
        self.support = User.objects.create_user(
            username="soporte@sestel.local",
            email="soporte@sestel.local",
            password="Sestel2026!",
            role=User.Role.SUPPORT,
        )
        self.support.teams.set([self.team, self.soporte_b])

    def create_ticket_through_api(self, contrato="10001", numero_ot=""):
        self.client.force_authenticate(self.dispatcher)
        response = self.client.post(
            "/api/tickets/",
            {
                "title": "ONT sin señal",
                "description": "La ONT permanece sin señal después de la activación.",
                "category": Ticket.Category.FTTH,
                "priority": Ticket.Priority.HIGH,
                "contrato": contrato,
                "numero_ot": numero_ot,
                "cliente_nombre": "Cliente Prueba",
                "nodo": "NODO-1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return Ticket.objects.get(pk=response.data["id"])

    def test_ticket_is_scoped_to_its_creator_for_dispatchers(self):
        ticket = self.create_ticket_through_api()
        self.assertEqual(ticket.creator, self.dispatcher)
        self.assertEqual(ticket.origin_team, self.team)

        self.client.force_authenticate(self.other_dispatcher)
        response = self.client.get("/api/tickets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        other_group, _ = WorkGroup.objects.get_or_create(name="Otro Grupo", defaults={"code": "otro-grupo-test"})
        other_team, _ = Team.objects.get_or_create(group=other_group, name="Otro Equipo", defaults={"code": "otro-equipo-test"})
        outsider = User.objects.create_user(username="outsider@sestel.local", email="outsider@sestel.local", password="Sestel2026!", role=User.Role.DISPATCHER)
        outsider.teams.set([other_team])
        self.client.force_authenticate(outsider)
        response2 = self.client.get("/api/tickets/")
        self.assertEqual(response2.data["count"], 0)

    def test_support_resolution_requires_creator_validation(self):
        ticket = self.create_ticket_through_api()
        self.client.force_authenticate(self.support)
        take_response = self.client.post(f"/api/tickets/{ticket.id}/take/")
        self.assertEqual(take_response.status_code, 200)
        resolve_response = self.client.post(
            f"/api/tickets/{ticket.id}/resolve/",
            {"resolution_notes": "Se ajustó el conector óptico y se verificó señal estable."},
            format="json",
        )
        self.assertEqual(resolve_response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.VALIDATION)

        self.client.force_authenticate(self.other_dispatcher)
        rejected_response = self.client.post(
            f"/api/tickets/{ticket.id}/validate/",
            {"approved": True},
            format="json",
        )
        self.assertEqual(rejected_response.status_code, 403)

        self.client.force_authenticate(self.dispatcher)
        approved_response = self.client.post(
            f"/api/tickets/{ticket.id}/validate/",
            {"approved": True, "comment": "Confirmado en campo."},
            format="json",
        )
        self.assertEqual(approved_response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.CLOSED)

    def test_automation_escalates_expired_tickets_and_closes_stale_validations(self):
        active = create_ticket(
            creator=self.dispatcher,
            title="Caso vencido",
            description="Ticket para probar la automatización de SLA.",
            category=Ticket.Category.FTTH,
            priority=Ticket.Priority.CRITICAL,
        )
        active.sla_due_at = timezone.now() - timedelta(minutes=1)
        active.save(update_fields=["sla_due_at", "updated_at"])

        validation = create_ticket(
            creator=self.dispatcher,
            title="Caso en validación",
            description="Ticket para probar el cierre automático.",
            category=Ticket.Category.FTTH,
            priority=Ticket.Priority.MEDIUM,
        )
        take_ticket(validation, self.support)
        resolve_ticket(validation, self.support, "La solución quedó aplicada correctamente.")
        validation.validation_due_at = timezone.now() - timedelta(minutes=1)
        validation.save(update_fields=["validation_due_at", "updated_at"])

        call_command("process_ticket_automation")
        active.refresh_from_db()
        validation.refresh_from_db()
        self.assertEqual(active.status, Ticket.Status.ESCALATED)
        self.assertEqual(validation.status, Ticket.Status.CLOSED)

    def test_creator_can_attach_a_png_evidence_file(self):
        ticket = self.create_ticket_through_api()
        evidence = SimpleUploadedFile("evidence.png", b"PNG test content", content_type="image/png")
        response = self.client.post(f"/api/tickets/{ticket.id}/attachments/", {"file": evidence}, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["original_name"], "evidence.png")

    def test_duplicate_contrato_or_ot_is_rejected(self):
        self.create_ticket_through_api(contrato="20001")
        self.client.force_authenticate(self.dispatcher)
        response = self.client.post(
            "/api/tickets/",
            {
                "title": "Duplicado",
                "description": "Mismo contrato.",
                "category": Ticket.Category.FTTH,
                "priority": Ticket.Priority.MEDIUM,
                "contrato": "20001",
                "cliente_nombre": "Cliente Prueba",
                "nodo": "NODO-1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("contrato", response.data)

    def test_support_can_escalate_complete_and_return(self):
        from .models import EscalationArea

        area, _ = EscalationArea.objects.get_or_create(name="NOC")
        ticket = self.create_ticket_through_api(contrato="", numero_ot="30001")
        self.client.force_authenticate(self.support)
        self.client.post(f"/api/tickets/{ticket.id}/take/")
        esc = self.client.post(
            f"/api/tickets/{ticket.id}/escalar/",
            {"area_id": area.id, "motivo": "Falla de planta externa.", "contrato": "40001"},
            format="json",
        )
        self.assertEqual(esc.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ESCALATED)
        self.assertEqual(ticket.contrato, "40001")
        self.assertEqual(ticket.estado_previo, Ticket.Status.IN_PROGRESS)

        self.client.force_authenticate(self.dispatcher)
        ins = self.client.post(
            f"/api/tickets/{ticket.id}/instruir/",
            {"instrucciones": "Retirar al técnico y confirmar ventana."},
            format="json",
        )
        self.assertEqual(ins.status_code, 200)

        self.client.force_authenticate(self.support)
        des = self.client.post(f"/api/tickets/{ticket.id}/desescalar/")
        self.assertEqual(des.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.IN_PROGRESS)